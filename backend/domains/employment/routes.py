# -*- coding: utf-8 -*-
"""就业对接域路由：岗位浏览与筛选、详情、相似推荐、证书与积分、投递、收藏。

从 app.py 迁出（后端按领域拆分 T15），URL、请求响应结构、状态码、错误码保持不变。

数据来源有两条，务必分清：

  · jobs         —— 企业端发布且**已通过审核**的岗位（可在站内申请 / 收藏）。
                    审核过滤在 `employment.get_job_listings_base()` 里，
                    学员端永远拿不到 `pending` 岗位（见该函数 docstring）；
  · recruitments —— 公开招聘（招募）公告，平台策展内容、**不做站内申请**，
                    卡片提供「查看公告」直达发布单位原文。T09 起读库
                    （db_domains.recruitments 的 recruitments / recruitment_sources
                    两张表，ADR 0002），代码里不再持有公告副本。

列表另下发 `category_options`（两类各自的真实条数）+ `recruit_hidden_by_salary`：
前端据此把分类下拉标出条数、并在「按薪资筛选时公告被隐藏」这件事上说清楚，
避免学员看到一整页「未找到匹配的职位」却不知道为什么（2026-10-07）。
"""

from flask import Blueprint, jsonify, request

from core.session import get_session_user
from shared.options import category_option_list
from shared.resume_state import user_has_resume
from db_domains import certificates, employment, points
from db_domains import recruitments as recruitments_db

employment_bp = Blueprint('employment', __name__)


def _session_identity(requested_user_id=''):
    """就业个人状态只能以会话用户身份读写。

    请求体里的 user_id 只用于兼容旧调用：如果传了就必须与当前会话一致；
    没传时直接采用会话用户，避免客户端通过替换 user_id 读写他人数据。
    """
    user = get_session_user()
    if not user:
        return None, (jsonify({"success": False, "message": "请先登录"}), 401)
    requested = str(requested_user_id or '').strip()
    if requested and requested != user['username']:
        return None, (jsonify({
            "success": False,
            "message": "无权访问他人的求职资料",
        }), 403)
    return user['username'], None


@employment_bp.route('/api/employment/jobs', methods=['GET'])
def get_jobs():
    """学员端职位列表（公开，免登录）。

    下发两部分，前端按 `source_type` 区分展示：
      · jobs         —— 企业端发布且**已通过审核**的岗位（可在站内申请 / 收藏）
      · recruitments —— 公开招聘（招募）公告（平台策展内容，**不做站内申请**，
                        卡片提供「查看公告」直达发布单位原文，读库见模块 docstring）

    注意：jobs 侧的审核过滤在 `employment.get_job_listings_base()` 里，
    学员端永远拿不到 `pending` 岗位 —— 见该函数 docstring。

    另下发 `category_options`（两类各自的真实条数）+ `salary_filtered_out`：
    前端据此把分类下拉标出条数、并在「按薪资筛选时公告被隐藏」这件事上说清楚，
    避免学员看到一整页「未找到匹配的职位」却不知道为什么（2026-10-07）。
    """
    keyword = request.args.get('keyword', '')
    location = request.args.get('location', '')
    salary_range = request.args.get('salary', '')
    category = request.args.get('category', '')

    # 先取「不含分类过滤」的基础集，才能统计每个分类各多少条
    # （若先按分类过滤，统计永远只剩当前选中的那一项）。
    jobs_base = employment.get_job_listings_base(keyword, location, salary_range)
    ent_counts = {}
    for j in jobs_base:
        c = (j.get('category') or '').strip() or '未分类'
        ent_counts[c] = ent_counts.get(c, 0) + 1
    jobs = [j for j in jobs_base if not category or (j.get('category') or '') == category]
    for j in jobs:
        j['source_type'] = 'enterprise'

    # 公开招聘公告：只按 关键词 / 地区 / 类别 过滤。
    # 公告没有「薪资」字段，所以薪资筛选对它不生效（前端也不展示该项）。
    kw = (keyword or '').strip()
    rec_pool, rec_counts = [], {}
    for r in recruitments_db.get_recruitments():
        if kw and (kw not in (r.get('title') or '')) and (kw not in (r.get('org') or '')) \
                and (kw not in (r.get('description') or '')):
            continue
        if location and location != r.get('region'):
            continue
        r['source_type'] = 'public_recruit'
        rec_pool.append(r)
        c = (r.get('category') or '').strip() or '未分类'
        rec_counts[c] = rec_counts.get(c, 0) + 1

    recruitments = [r for r in rec_pool if not category or r.get('category') == category]

    notes = recruitments_db.get_recruitment_notes()
    return jsonify({
        "success": True,
        "jobs": jobs,
        "recruitments": recruitments,
        "recruit_source_note": notes['source_note'],
        "recruit_disclaimer": notes['disclaimer'],
        # 分类下拉：两组各自真实的条数（口径 = 已应用 关键词/地点/薪资，未应用分类）
        "category_options": {
            "enterprise": category_option_list(ent_counts, employment.ENTERPRISE_JOB_CATEGORIES),
            "recruit": category_option_list(rec_counts, recruitments_db.RECRUIT_CATEGORIES),
        },
        # 薪资筛选对公告不生效，被隐藏的公告条数 —— 前端据此给出明确说明
        "recruit_hidden_by_salary": len(rec_pool) if salary_range else 0,
        # 尚未过审的企业岗位条数。企业发布的岗位要经管理员审核才露出，
        # 若此刻一条都没通过，学员端应说明「岗位审核中」而不是「没有岗位」。
        "enterprise_review_pending": employment.count_pending_job_listings(),
    })


@employment_bp.route('/api/employment/jobs/<int:job_id>', methods=['GET'])
def get_job_detail(job_id):
    job = employment.get_job_by_id(job_id)
    # 未通过审核的岗位对学员端等同「不存在」——
    # 否则随便猜个 id 就能看到 pending 岗位，审核门禁被直链绕过。
    if not job or (job.get('review_status') or '') != 'approved':
        return jsonify({"success": False, "message": "职位不存在或尚未通过审核"}), 404
    return jsonify({"success": True, "job": job})


@employment_bp.route('/api/employment/jobs/<int:job_id>/similar', methods=['GET'])
def get_similar_jobs(job_id):
    job = employment.get_job_by_id(job_id)
    if not job or (job.get('review_status') or '') != 'approved':
        return jsonify({"success": True, "jobs": []})
    similar = employment.get_similar_jobs(job_id, job.get('category', ''), 3)
    return jsonify({"success": True, "jobs": similar})


@employment_bp.route('/api/employment/certificates/<user_id>', methods=['GET'])
def get_certificates(user_id):
    user_id, err = _session_identity(user_id)
    if err:
        return err
    certs = certificates.get_certificates(user_id)
    return jsonify({"success": True, "certificates": certs})


@employment_bp.route('/api/employment/points/<user_id>', methods=['GET'])
def get_points(user_id):
    user_id, err = _session_identity(user_id)
    if err:
        return err
    pts = points.get_points(user_id)
    return jsonify({"success": True, "points": pts['balance'], "history": pts['history']})


@employment_bp.route('/api/employment/exchange', methods=['POST'])
def exchange_points():
    data = request.get_json(silent=True) or {}
    user_id, err = _session_identity(data.get('user_id'))
    if err:
        return err
    item = str(data.get('item') or '商品').strip()[:100] or '商品'
    cost = data.get('cost', 0)
    if isinstance(cost, bool) or not isinstance(cost, int) or cost <= 0:
        return jsonify({
            "success": False,
            "message": "兑换积分必须为正整数",
        }), 400

    new_balance = points.update_points(user_id, -cost, f"兑换{item}")
    if new_balance == -1:
        return jsonify({"success": False, "message": "积分不足"})
    return jsonify({"success": True, "message": f"成功兑换：{item}", "remaining_points": new_balance})


@employment_bp.route('/api/employment/apply', methods=['POST'])
def apply_job():
    """申请职位"""
    data = request.get_json(silent=True) or {}
    job_id = data.get('job_id')
    user_id, err = _session_identity(data.get('user_id'))
    if err:
        return err

    if not job_id:
        return jsonify({"success": False, "message": "参数不完整"})

    result = employment.apply_for_job(user_id, job_id)
    if result == 'ok':
        # 申请成功加积分
        points.update_points(user_id, 20, "申请职位奖励")
        return jsonify({"success": True, "message": "申请成功！已获得20积分奖励",
                        # 前端据此在提示里补一句「你还没有填写简历」——
                        # 否则学员以为简历已经随申请投出去了（2026-10-07）。
                        # 口径由就业能力档案域持有，本域显式引用（见该函数的归属说明）。
                        "has_resume": user_has_resume(user_id)})
    if result == 'dup':
        return jsonify({"success": False, "message": "您已申请过该职位"})
    # 'unavailable'：职位不存在或未通过审核
    return jsonify({"success": False, "message": "该职位不存在或尚未通过审核，无法申请"})


@employment_bp.route('/api/employment/applications/<user_id>', methods=['GET'])
def get_user_applications(user_id):
    user_id, err = _session_identity(user_id)
    if err:
        return err
    status_filter = request.args.get('status', '')
    apps = employment.get_user_applications(user_id, status_filter)
    return jsonify({"success": True, "applications": apps})


@employment_bp.route('/api/employment/applications/<user_id>/counts', methods=['GET'])
def get_application_counts(user_id):
    user_id, err = _session_identity(user_id)
    if err:
        return err
    counts = employment.get_application_counts(user_id)
    return jsonify({"success": True, "counts": counts})


@employment_bp.route('/api/employment/save', methods=['POST'])
def save_job():
    data = request.get_json(silent=True) or {}
    job_id = data.get('job_id')
    user_id, err = _session_identity(data.get('user_id'))
    if err:
        return err
    if not job_id:
        return jsonify({"success": False, "message": "参数不完整"})
    success = employment.save_job(user_id, job_id)
    if success:
        return jsonify({"success": True, "message": "收藏成功"})
    return jsonify({"success": False, "message": "已收藏过该职位"})


@employment_bp.route('/api/employment/save', methods=['DELETE'])
def unsave_job():
    data = request.get_json(silent=True) or {}
    job_id = data.get('job_id')
    user_id, err = _session_identity(data.get('user_id'))
    if err:
        return err
    if not job_id:
        return jsonify({"success": False, "message": "参数不完整"})
    employment.unsave_job(user_id, job_id)
    return jsonify({"success": True, "message": "已取消收藏"})


@employment_bp.route('/api/employment/saved/<user_id>', methods=['GET'])
def get_saved_jobs(user_id):
    user_id, err = _session_identity(user_id)
    if err:
        return err
    saved_ids = employment.get_saved_jobs(user_id)
    return jsonify({"success": True, "saved_ids": saved_ids})


@employment_bp.route('/api/employment/stats/<user_id>', methods=['GET'])
def get_employment_stats(user_id):
    user_id, err = _session_identity(user_id)
    if err:
        return err
    stats = employment.get_employment_stats(user_id)
    return jsonify({"success": True, "stats": stats})
