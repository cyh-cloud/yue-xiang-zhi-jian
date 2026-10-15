# -*- coding: utf-8 -*-
"""企业域路由：岗位管理、投递处理与统计。

从 app.py 迁出（后端按领域拆分 T17），URL、请求响应结构、状态码、错误码保持不变。

三条口径：

- 发布即 pending，且改内容后重新走审核（否则「先发合规的骗过审核、通过后再改成
  违规内容」会绕过整条审核链路）；
- 删除只认归属：只能删自己发布的岗位；
- 「在招职位」只算审核通过的，未通过的单列 pending_jobs。

角色把关走能力表（core.permissions.require_capability），不再逐处写角色名比较。
本域的岗位增删改与统计都挂在 job.manage 上。
"""

import json

from flask import Blueprint, jsonify, request

from core.permissions import require_capability
from core.session import get_session_user
from db_connection import get_connection
from db_domains import reviews


enterprise_bp = Blueprint('enterprise', __name__)


@enterprise_bp.route('/api/enterprise/jobs', methods=['GET'])
@require_capability('job.manage')
def enterprise_get_jobs():
    user = get_session_user()
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM job_listings WHERE enterprise_id = ? ORDER BY posted_at DESC",
        (user['username'],)).fetchall()
    conn.close()
    jobs = []
    for r in rows:
        d = dict(r)
        d['requirements'] = json.loads(d['requirements'])
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
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO job_listings (title, company, salary, requirements, description, "
        "location, category, job_type, education, experience, company_size, industry, "
        "enterprise_id, review_status, posted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))",
        (data.get('title', ''), user.get('company_name', data.get('company', '')),
         data.get('salary', ''), json.dumps(data.get('requirements', [])),
         data.get('description', ''), data.get('location', ''),
         data.get('category', ''), data.get('job_type', '全职'),
         data.get('education', ''), data.get('experience', ''),
         user.get('company_name', ''), data.get('industry', ''),
         user['username'], 'pending'))
    conn.commit()
    job_id = cursor.lastrowid
    conn.close()
    reviews.create_content_review('job', job_id, user['username'])
    return jsonify({"success": True, "id": job_id, "message": "职位发布成功，等待审核"})


@enterprise_bp.route('/api/enterprise/jobs/<int:job_id>', methods=['PUT'])
@require_capability('job.manage')
def enterprise_update_job(job_id):
    user = get_session_user()
    data = request.get_json()
    conn = get_connection()
    updates = []
    params = []
    for k in ('title', 'company', 'salary', 'description', 'location',
              'category', 'job_type', 'education', 'experience', 'industry'):
        if k in data and data[k] is not None:
            updates.append(f"{k}=?"); params.append(data[k])
    if 'requirements' in data:
        updates.append("requirements=?"); params.append(json.dumps(data['requirements']))
    if updates:
        # 内容改了就重新走审核：否则「先发一条合规的骗过审核、通过后再改成违规内容」
        # 会绕过整个审核链路。改回 pending 并新开一条审核记录。
        updates.append("review_status=?")
        params.append('pending')
        params.append(job_id)
        conn.execute(f"UPDATE job_listings SET {', '.join(updates)} WHERE id=?", params)
        conn.commit()
    conn.close()
    if updates:
        reviews.create_content_review('job', job_id, user['username'])
        return jsonify({"success": True, "message": "更新成功，需重新审核"})
    return jsonify({"success": True, "message": "更新成功"})


@enterprise_bp.route('/api/enterprise/jobs/<int:job_id>', methods=['DELETE'])
@require_capability('job.manage')
def enterprise_delete_job(job_id):
    user = get_session_user()
    conn = get_connection()
    # 只能删自己发布的岗位（此前不校验归属，任何企业账号都能按 id 删别人的岗位）
    row = conn.execute("SELECT enterprise_id FROM job_listings WHERE id = ?", (job_id,)).fetchone()
    if not row or row['enterprise_id'] != user['username']:
        conn.close()
        return jsonify({"success": False, "message": "职位不存在或无权操作"}), 404
    conn.execute("DELETE FROM job_listings WHERE id = ?", (job_id,))
    conn.execute("DELETE FROM saved_jobs WHERE job_id = ?", (job_id,))
    conn.execute("DELETE FROM content_reviews WHERE content_type = 'job' AND content_id = ?", (job_id,))
    conn.commit()
    conn.close()
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
    conn = get_connection()
    # ⚠️ 原先只 JOIN users，**没有 JOIN resumes** → 企业端只能看到申请人姓名/电话/邮箱，
    #   学员在「我的简历」里填的意向岗位、学历、年限、技能、经历**企业完全看不到**，
    #   「简历管理」名不副实（2026-10-09）。这里 LEFT JOIN 补上，学员没填简历时
    #   resume_* 全为 NULL，前端如实显示「未填写」，不做任何补白。
    rows = conn.execute("""
        SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
               jl.title as job_title,
               u.name as applicant_name, u.phone as applicant_phone,
               u.email as applicant_email, u.bio as applicant_bio,
               r.title as resume_title, r.region as resume_region,
               r.education as resume_education, r.work_years as resume_work_years,
               r.phone as resume_phone, r.email as resume_email,
               r.self_eval as resume_self_eval, r.skills as resume_skills,
               r.experience as resume_experience, r.updated_at as resume_updated_at
        FROM job_applications ja
        JOIN job_listings jl ON ja.job_id = jl.id
        JOIN users u ON ja.user_id = u.username
        LEFT JOIN resumes r ON r.user_id = ja.user_id
        WHERE jl.enterprise_id = ?
        ORDER BY ja.applied_at DESC
    """, (user['username'],)).fetchall()
    conn.close()
    return jsonify({"success": True, "applications": [dict(r) for r in rows]})


@enterprise_bp.route('/api/enterprise/applications/<int:app_id>', methods=['PUT'])
@require_capability('job.manage')
def enterprise_update_application(app_id):
    user = get_session_user()
    data = request.get_json()
    new_status = data.get('status', '')
    if new_status not in ('approved', 'rejected', 'interview'):
        return jsonify({"success": False, "message": "无效的状态"}), 400
    conn = get_connection()
    conn.execute("UPDATE job_applications SET status = ? WHERE id = ?", (new_status, app_id))
    conn.commit()
    conn.close()
    status_labels = {'approved': '已通过', 'rejected': '已拒绝', 'interview': '已通知面试'}
    return jsonify({"success": True, "message": f"状态已更新为：{status_labels.get(new_status, new_status)}"})


@enterprise_bp.route('/api/enterprise/stats', methods=['GET'])
@require_capability('job.manage')
def enterprise_get_stats():
    user = get_session_user()
    conn = get_connection()
    # ⚠️ 「在招职位」只算**审核通过**的：企业刚发布的岗位是 `pending`，学员端只展示
    #    `review_status='approved'`（见 get_job_listings_base）。若这里把未审核岗位也数进去，
    #    企业会以为岗位已经对外可见 —— 与「职位管理」列表/学员端口径必须一致。
    total_jobs = conn.execute(
        "SELECT COUNT(*) FROM job_listings WHERE enterprise_id = ? AND review_status = 'approved'",
        (user['username'],)).fetchone()[0]
    # 未通过审核的（pending / rejected）单列，让企业知道有几个岗位在排队或被打回。
    # COALESCE 是 fail-safe：历史行若 review_status 为 NULL，也按「未通过」计，不会漏报。
    pending_jobs = conn.execute(
        "SELECT COUNT(*) FROM job_listings WHERE enterprise_id = ? "
        "AND COALESCE(review_status, '') != 'approved'",
        (user['username'],)).fetchone()[0]
    total_apps = conn.execute("""
        SELECT COUNT(*) FROM job_applications ja
        JOIN job_listings jl ON ja.job_id = jl.id
        WHERE jl.enterprise_id = ?
    """, (user['username'],)).fetchone()[0]
    conn.close()
    return jsonify({"success": True, "stats": {
        "total_jobs": total_jobs,
        "pending_jobs": pending_jobs,
        "total_applications": total_apps
    }})
