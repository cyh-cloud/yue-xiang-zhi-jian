# -*- coding: utf-8 -*-
"""教学支撑域路由：公告、实训批改、学情分析、课程与材料、3D 模型。

从 app.py 迁出（后端按领域拆分 T16），URL、请求响应结构、状态码、错误码保持不变。

与教师管理域（domains.teacher）的分界按 spec 的「切分单位」一节：本域管「教学内容
与教学过程」这一侧（公告、批改、学情、课程、材料、3D 模型），名册与账号绑定属
教师管理域。两者共用 `/api/teacher/*` 前缀但分属不同领域，因此是两个蓝图对象。

一个领域一个蓝图（docs/adr/0001），蓝图对象 teaching_support_bp 定义在本文件。

跨域边界：

- 会话取用户与角色装饰器只用共享层 core.session（require_role / get_session_user）。
  ⚠️ 本域存在两种把关写法，且**都不能改**：公告、批改、实训列表、学情分析、
  3D 模型走 `@require_role(...)` 装饰器（未登录 401 / 角色不符 403）；课程与材料
  这几条是函数内 inline 的 `get_session_user()` + 角色判断（未登录与角色不符都是 403）。
  这是拆分前就有的差异，统一它会改变对外可见的状态码。
- 数据访问一律走 database 契约层（db_domains/teaching.py、db_domains/courses.py）；
- 上传落盘目录与静态资源放行目录同源于仓库根（core.app_factory.BASE_DIR），
  否则会出现「存得下却取不回」。
"""

import json
import os
from datetime import datetime

from flask import Blueprint, jsonify, request

from core.app_factory import BASE_DIR
from core.session import TEACHER_ROLES, get_session_user, require_role
import database
from shared.training_status import training_status_label

teaching_support_bp = Blueprint('teaching_support', __name__)

# 3D 模型上传：允许的文件格式（仅常见 3D 格式）
_MODEL_3D_EXTS = ('glb', 'gltf', 'obj', 'fbx', 'stl', 'dae', 'ply', 'usdz')
# 单个模型文件大小上限 50MB
_MODEL_3D_MAX_BYTES = 50 * 1024 * 1024


# ==================== 通知公告 ====================

@teaching_support_bp.route('/api/teacher/announcements', methods=['GET'])
@require_role(*TEACHER_ROLES)
def get_announcements():
    announcements = database.get_announcements()
    return jsonify({"success": True, "announcements": announcements})


@teaching_support_bp.route('/api/teacher/announcements', methods=['POST'])
@require_role(*TEACHER_ROLES)
def create_announcement():
    data = request.get_json()
    title = data.get('title', '')
    content = data.get('content', '')
    category = data.get('category', '通知')
    pinned = 1 if data.get('pinned') else 0
    if not title or not content:
        return jsonify({"success": False, "message": "请填写标题和内容"})
    aid = database.create_announcement(title, content, category, pinned)
    # 自动给所有学员发通知
    database.create_notification_for_all_students(
        'announcement', f'新{category}', title, 'announcement', aid
    )
    return jsonify({"success": True, "message": "发布成功", "id": aid})


@teaching_support_bp.route('/api/teacher/announcements/<int:ann_id>', methods=['DELETE'])
@require_role(*TEACHER_ROLES)
def delete_announcement(ann_id):
    if database.delete_announcement(ann_id):
        return jsonify({"success": True, "message": "删除成功"})
    return jsonify({"success": False, "message": "未找到通知"})


# ==================== 学员个人数据 ====================

# 2026-10-07：「发布作业」整块下架，`/api/student/submissions`（我的作业提交）
# 与它配套的教师侧 `/api/teacher/submissions/<id>` 一并删除 —— 前端零调用，
# 学员端的「我的作业」面板已在 v55 下架；三种实训的历史记录走 /api/ecommerce/*/records。


@teaching_support_bp.route('/api/student/announcements', methods=['GET'])
def get_my_announcements():
    """获取通知公告列表（学员可见）"""
    announcements = database.get_announcements(limit=30)
    return jsonify({"success": True, "announcements": announcements})


# ==================== 实训批改 ====================
# 2026-10-07 用户拍板：**「发布作业」整块下架**（`POST|GET /api/teacher/assignments`、
# `GET /api/teacher/assignments/<id>` 三条路由删除，前端本来就零调用）。
# 保留的只有批改：三种电商实训（直播/文案/客服）复用 assignments 表当题目载体，
# 学员提交落在 assignment_submissions，教师在这里批改。
# ⚠️ 顺带解决了一个真实缺陷：原「发布作业」按方向通知学员时，比较的是
#    `assignments.direction`（英文 slug 'ecommerce'）与 `students.direction`（中文
#    '电商运营'），两者永不相等 → 通知一个也发不出去。该逻辑随本块一并删除。
@teaching_support_bp.route('/api/teacher/assignments/grade', methods=['POST'])
@require_role(*TEACHER_ROLES)
def grade_submission():
    data = request.get_json()
    submission_id = data.get('submission_id')
    score = data.get('score')
    feedback = data.get('feedback', '')
    if submission_id is None or score is None:
        return jsonify({"success": False, "message": "请填写批改信息"})
    # 获取提交信息以发送通知
    conn = database.get_connection()
    sub = conn.execute("SELECT student_id, assignment_id FROM assignment_submissions WHERE id = ?", (submission_id,)).fetchone()
    conn.close()
    if database.grade_submission(submission_id, score, feedback):
        if sub:
            database.create_notification(sub['student_id'], 'grade', '实训已批改', f'得分：{score}', 'assignment', sub['assignment_id'])
        return jsonify({"success": True, "message": "批改成功"})
    return jsonify({"success": False, "message": "批改失败"})


@teaching_support_bp.route('/api/teacher/trainings', methods=['GET'])
@require_role(*TEACHER_ROLES)
def teacher_get_trainings():
    """教师端「实训提交」页：全部学员的电商实训提交（直播/文案/客服）。

    数据来自 assignment_submissions（学生端 /api/ecommerce/{live,copy,cs}/submit 写入）。
    批改仍走既有 /api/teacher/assignments/grade，会给学员发站内通知。
    """
    out = []
    for r in database.get_all_trainings():
        detail = {}
        try:
            detail = json.loads(r.get('content') or '{}')
        except Exception:
            detail = {}
        if not isinstance(detail, dict):
            detail = {}
        # ⚠️ 学生作品正文必须下发，否则教师端就是「盲批」：
        #    直播/文案形态是 script，客服对练形态是 transcript（[{role,content}]）。
        #    2026-10-07 前这里只给了 product/attempts/score，教师只能凭「类型+产品」猜分。
        script = str(detail.get('script') or '')
        transcript = detail.get('transcript')
        if not isinstance(transcript, list):
            transcript = []
        meta = detail.get('meta')
        if not isinstance(meta, dict):
            meta = {}
        out.append({
            "id": r.get('id'),
            "student_id": r.get('student_id'),
            "student_name": r.get('student_name') or '',
            "assignment_id": r.get('assignment_id'),
            "assignment_title": r.get('assignment_title') or '',
            "kind": r.get('kind') or '',
            "product": str(detail.get('product') or ''),
            "attempts": detail.get('attempts') or 1,
            # score = 教师批改分（未批改为 None）；rule_score = 系统规则分（存 content 里）
            "score": r.get('score'),
            "rule_score": detail.get('rule_score'),
            "script": script,
            "transcript": transcript,
            "meta": meta,
            "script_len": len(script),
            "feedback": r.get('feedback') or '',
            "status": r.get('status') or 'submitted',
            "status_label": training_status_label(r.get('status')),
            "submitted_at": r.get('submitted_at') or '',
            "graded_at": r.get('graded_at') or '',
            "regrade_needed": (r.get('status') or '') == 'resubmitted',
        })
    pending_regrade = sum(1 for x in out if x['regrade_needed'])
    return jsonify({"success": True, "trainings": out, "pending_regrade": pending_regrade})


# ==================== 学情分析 ====================

@teaching_support_bp.route('/api/teacher/analytics', methods=['GET'])
@require_role(*TEACHER_ROLES)
def get_analytics():
    data = database.get_analytics_data()
    return jsonify({"success": True, "analytics": data})


# ==================== 课程管理 ====================

@teaching_support_bp.route('/api/teacher/courses', methods=['GET'])
def teacher_get_courses():
    user = get_session_user()
    if not user or user['role'] not in ('teacher', 'super_admin'):
        return jsonify({"success": False, "message": "权限不足"}), 403
    courses = database.get_courses(teacher_id=user['username'], published_only=False)
    return jsonify({"success": True, "courses": courses})


@teaching_support_bp.route('/api/teacher/courses', methods=['POST'])
def teacher_create_course():
    user = get_session_user()
    if not user or user['role'] != 'teacher':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json()
    course_id = database.create_course(
        data.get('title', ''), data.get('description', ''),
        data.get('category', ''), user['username'],
        data.get('cover_url', ''))
    return jsonify({"success": True, "id": course_id, "message": "课程创建成功，等待审核"})


@teaching_support_bp.route('/api/teacher/courses/<int:course_id>', methods=['PUT'])
def teacher_update_course(course_id):
    user = get_session_user()
    if not user or user['role'] != 'teacher':
        return jsonify({"success": False, "message": "权限不足"}), 403
    data = request.get_json()
    database.update_course(course_id, **{k: v for k, v in data.items()
        if k in ('title', 'description', 'category', 'cover_url')})
    return jsonify({"success": True, "message": "更新成功"})


@teaching_support_bp.route('/api/teacher/courses/<int:course_id>', methods=['DELETE'])
def teacher_delete_course(course_id):
    user = get_session_user()
    if not user or user['role'] != 'teacher':
        return jsonify({"success": False, "message": "权限不足"}), 403
    database.delete_course(course_id)
    return jsonify({"success": True, "message": "删除成功"})


# ==================== 课程素材 ====================

@teaching_support_bp.route('/api/teacher/courses/<int:course_id>/materials', methods=['GET'])
def teacher_get_materials(course_id):
    materials = database.get_course_materials(course_id)
    return jsonify({"success": True, "materials": materials})


@teaching_support_bp.route('/api/teacher/courses/<int:course_id>/materials', methods=['POST'])
def teacher_add_material(course_id):
    user = get_session_user()
    if not user or user['role'] != 'teacher':
        return jsonify({"success": False, "message": "权限不足"}), 403
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "请选择文件"}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({"success": False, "message": "文件名为空"}), 400
    # 保存文件
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{f.filename}"
    filepath = os.path.join('uploads', 'courses', str(course_id), filename)
    os.makedirs(os.path.dirname(os.path.join(BASE_DIR, filepath)), exist_ok=True)
    f.save(os.path.join(BASE_DIR, filepath))
    # 判断类型
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext in ('mp4', 'avi', 'mov', 'webm', 'mkv'):
        mtype = 'video'
    elif ext == 'pdf':
        mtype = 'pdf'
    else:
        mtype = 'other'
    mat_id = database.add_course_material(course_id, mtype, f.filename, filepath)
    return jsonify({"success": True, "id": mat_id, "message": "上传成功"})


@teaching_support_bp.route('/api/teacher/materials/<int:mat_id>', methods=['DELETE'])
def teacher_delete_material(mat_id):
    user = get_session_user()
    if not user or user['role'] != 'teacher':
        return jsonify({"success": False, "message": "权限不足"}), 403
    filepath = database.delete_course_material(mat_id)
    if filepath:
        full = os.path.join(BASE_DIR, filepath)
        if os.path.exists(full):
            os.remove(full)
    return jsonify({"success": True, "message": "删除成功"})


# ==================== 3D 模型管理 ====================

@teaching_support_bp.route('/api/teacher/models-3d', methods=['GET'])
@require_role(*TEACHER_ROLES)
def teacher_get_models_3d():
    user = get_session_user()
    models = database.get_models_3d(teacher_id=user['username'] if user['role'] == 'teacher' else None,
                                    published_only=False)
    return jsonify({"success": True, "models": models})


@teaching_support_bp.route('/api/teacher/models-3d', methods=['POST'])
@require_role('teacher')
def teacher_create_model_3d():
    user = get_session_user()
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "请选择模型文件"}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({"success": False, "message": "文件名为空"}), 400
    # 文件类型校验：仅允许常见 3D 模型格式
    ext = os.path.splitext(f.filename)[1].lower().lstrip('.')
    if ext not in _MODEL_3D_EXTS:
        return jsonify({"success": False, "message": "不支持的文件格式，仅支持 glb/gltf/obj/fbx/stl/dae/ply/usdz"}), 400
    title = request.form.get('title', f.filename)
    description = request.form.get('description', '')
    craft_type = request.form.get('craft_type', '')
    # 保存文件
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{f.filename}"
    filepath = os.path.join('uploads', 'models_3d', filename)
    os.makedirs(os.path.dirname(os.path.join(BASE_DIR, filepath)), exist_ok=True)
    save_full = os.path.join(BASE_DIR, filepath)
    f.save(save_full)
    # 记录真实文件大小（上限 50MB，超限删除并拒绝）
    file_size = os.path.getsize(save_full) if os.path.exists(save_full) else 0
    if file_size > _MODEL_3D_MAX_BYTES:
        if os.path.exists(save_full):
            os.remove(save_full)
        return jsonify({"success": False, "message": "文件过大，模型文件不能超过 50MB"}), 400
    model_id = database.create_model_3d(title, description, craft_type,
                                         filepath, f.filename, file_size, user['username'])
    return jsonify({"success": True, "id": model_id, "message": "3D模型上传成功，等待审核"})


@teaching_support_bp.route('/api/teacher/models-3d/<int:model_id>', methods=['DELETE'])
@require_role('teacher')
def teacher_delete_model_3d(model_id):
    filepath = database.delete_model_3d(model_id)
    if filepath:
        full = os.path.join(BASE_DIR, filepath)
        if os.path.exists(full):
            os.remove(full)
    return jsonify({"success": True, "message": "删除成功"})