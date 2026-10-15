# -*- coding: utf-8 -*-
"""企业域路由：岗位管理、投递处理与统计。

从 app.py 迁出（后端按领域拆分 T17），URL、请求响应结构、状态码、错误码保持不变。
T11 起六处直连 SQL 收进就业域数据模块，两处跨四表 / 两表的 JOIN 改走视图
（v_enterprise_applications / v_enterprise_job_stats），响应结构不变。

三条口径：

- 发布即 pending，且改内容后重新走审核（否则「先发合规的骗过审核、通过后再改成
  违规内容」会绕过整条审核链路）；
- 删除只认归属：只能删自己发布的岗位；
- 「在招职位」只算审核通过的，未通过的单列 pending_jobs。

角色把关走能力表（core.permissions.require_capability），不再逐处写角色名比较。
本域的岗位增删改与统计都挂在 job.manage 上。
"""

from flask import Blueprint, jsonify, request

from core.permissions import require_capability
from core.session import get_session_user
from db_domains import employment, reviews


enterprise_bp = Blueprint('enterprise', __name__)


@enterprise_bp.route('/api/enterprise/jobs', methods=['GET'])
@require_capability('job.manage')
def enterprise_get_jobs():
    user = get_session_user()
    rows = employment.get_enterprise_jobs(user['username'])
    jobs = []
    for r in rows:
        d = dict(r)
        # requirements 由就业域解析成列表，域路由不再碰 JSON
        # 附上最近一次审核记录：企业需要知道「是否被驳回、为什么」才能修改重投。
        # 只给一个「已驳回」状态、不给理由，企业只能干等（2026-10-07 补）。
        review = reviews.get_review_by_content('job', d['id'])
        d['review_comment'] = (review or {}).get('review_comment') or ''
        d['reviewed_at'] = (review or {}).get('reviewed_at') or ''
        jobs.append(d)
    return jsonify({"success": True, "jobs": jobs})


@enterprise_bp.route('/api/enterprise/jobs', methods=['POST'])
@require_capability('job.manage')
def enterprise_create_job():
    user = get_session_user()
    data = request.get_json()
    job_id = employment.create_enterprise_job(
        data, user['username'], user.get('company_name', ''))
    reviews.create_content_review('job', job_id, user['username'])
    return jsonify({"success": True, "id": job_id, "message": "职位发布成功，等待审核"})


@enterprise_bp.route('/api/enterprise/jobs/<int:job_id>', methods=['PUT'])
@require_capability('job.manage')
def enterprise_update_job(job_id):
    user = get_session_user()
    data = request.get_json()
    # 内容改了就重新走审核：否则「先发一条合规的骗过审核、通过后再改成违规内容」
    # 会绕过整个审核链路。改回 pending 并新开一条审核记录，逻辑收在就业域里。
    updated = employment.update_enterprise_job(job_id, data)
    if updated:
        reviews.create_content_review('job', job_id, user['username'])
        return jsonify({"success": True, "message": "更新成功，需重新审核"})
    return jsonify({"success": True, "message": "更新成功"})


@enterprise_bp.route('/api/enterprise/jobs/<int:job_id>', methods=['DELETE'])
@require_capability('job.manage')
def enterprise_delete_job(job_id):
    user = get_session_user()
    # 只能删自己发布的岗位（此前不校验归属，任何企业账号都能按 id 删别人的岗位）
    owner = employment.get_job_owner(job_id)
    if owner != user['username']:
        return jsonify({"success": False, "message": "职位不存在或无权操作"}), 404
    employment.delete_job_and_dependents(job_id)
    # 审核记录属 reviews 域（content_reviews 是共享表），跨域删除只走它一个入口
    reviews.delete_reviews_for('job', job_id)
    return jsonify({"success": True, "message": "删除成功"})


# ---- 求购管理：2026-10-06 用户拍板「供应链求购不做」，整块下线 ----
# 原 /api/enterprise/procurements 的 GET/POST/PUT/DELETE 四个接口连同企业端
# 「求购管理」页面一起移除。数据层（procurements 表与 database 的 CRUD）保留不动 ——
# 只下线对外入口，不做破坏性迁移；`/api/admin/reviews` 也不再下发求购待审项。


# ---- 简历管理 ----

@enterprise_bp.route('/api/enterprise/applications', methods=['GET'])
@require_capability('job.manage')
def enterprise_get_applications():
    user = get_session_user()
    # ⚠️ 这条链路必须带出简历：学员在「我的简历」里填的意向岗位、学历、年限、
    #   技能、经历企业端要能看到，否则「简历管理」名不副实（2026-10-09）。
    #   四表 JOIN 收在 v_enterprise_applications 里；学员没填简历时 resume_*
    #   全为 NULL，前端如实显示「未填写」，不做任何补白。
    applications = employment.get_enterprise_applications(user['username'])
    return jsonify({"success": True, "applications": applications})


@enterprise_bp.route('/api/enterprise/applications/<int:app_id>', methods=['PUT'])
@require_capability('job.manage')
def enterprise_update_application(app_id):
    user = get_session_user()
    data = request.get_json()
    new_status = data.get('status', '')
    if new_status not in ('approved', 'rejected', 'interview'):
        return jsonify({"success": False, "message": "无效的状态"}), 400
    employment.set_job_application_status(app_id, new_status)
    status_labels = {'approved': '已通过', 'rejected': '已拒绝', 'interview': '已通知面试'}
    return jsonify({"success": True, "message": f"状态已更新为：{status_labels.get(new_status, new_status)}"})


@enterprise_bp.route('/api/enterprise/stats', methods=['GET'])
@require_capability('job.manage')
def enterprise_get_stats():
    user = get_session_user()
    # ⚠️ 「在招职位」只算**审核通过**的：企业刚发布的岗位是 `pending`，学员端只展示
    #    `review_status='approved'`（见 get_job_listings_base）。若这里把未审核岗位也数进去，
    #    企业会以为岗位已经对外可见 —— 与「职位管理」列表/学员端口径必须一致。
    #    未通过审核的（pending / rejected）单列，COALESCE 兜住历史 NULL 行。
    #    分组计数走 v_enterprise_job_stats，口径与视图定义同住一处。
    stats = employment.get_enterprise_stats(user['username'])
    return jsonify({"success": True, "stats": {
        "total_jobs": stats['total_jobs'],
        "pending_jobs": stats['pending_jobs'],
        "total_applications": stats['total_applications']
    }})
