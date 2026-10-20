# -*- coding: utf-8 -*-
"""教学支撑域路由：公告、实训批改、学情分析、课程与材料、3D 模型。

从 app.py 迁出（后端按领域拆分 T16），URL、请求响应结构、状态码、错误码保持不变。

与教师管理域（domains.teacher）的分界按 spec 的「切分单位」一节：本域管「教学内容
与教学过程」这一侧（公告、批改、学情、课程、材料、3D 模型），名册与账号绑定属
教师管理域。两者共用 `/api/teacher/*` 前缀但分属不同领域，因此是两个蓝图对象。

一个领域一个蓝图（docs/adr/0001），蓝图对象 teaching_support_bp 定义在本文件。

跨域边界：

- 会话取用户与角色把关只用共享层：core.session（get_session_user）与
  core.permissions（require_capability）。
  ⚠️ 本域的未登录状态码仍按拆分前的两种形状分流，`require_capability` 的
  anonymous 参数就是为这件事留的：公告/批改/实训/学情/3D 模型五条原本走
  `@require_role`（未登录 401），传 anonymous=401；课程与材料几条原本是
  inline 守卫（未登录与角色不符都是 403），用默认的 403。合起来会改变对外状态码。
- 数据访问一律走 database 契约层（db_domains/teaching.py、db_domains/courses.py）；
- 上传落盘目录与静态资源放行目录同源于仓库根（core.app_factory.BASE_DIR），
  否则会出现「存得下却取不回」。
"""

import json
import os
from datetime import datetime

from flask import Blueprint, jsonify, request

from core.app_factory import BASE_DIR
from core.permissions import STUDENT, SUPER_ADMIN, require_capability
from core.session import get_session_user
from shared.training_status import training_status_label
from shared.upload_limits import (
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MEGABYTES,
    MODEL_3D_EXTENSIONS,
)
from db_domains import notifications, reviews as reviews_db, teaching
from db_domains import courses as courses_db
from db_domains import students as students_db

CAPABILITIES_USED = ('notification.read', 'review.read')

teaching_support_bp = Blueprint('teaching_support', __name__)

# 3D 模型上传：允许的文件格式来自共享层，前端提示取同一份定义。
_MODEL_3D_EXTS = MODEL_3D_EXTENSIONS
MODEL_3D_FORMAT_MESSAGE = (
    "不支持的文件格式，仅支持 " + "/".join(MODEL_3D_EXTENSIONS)
)
# 单个模型文件大小上限，与应用级上传上限共用同一常量。
_MODEL_3D_MAX_BYTES = MAX_UPLOAD_BYTES


def _teacher_scope(user=None):
    current = user or get_session_user() or {}
    if current.get('role') == SUPER_ADMIN:
        return None
    return current.get('username') or ''


def _course_owner_error(course_id):
    course = courses_db.get_course(course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404
    scope = _teacher_scope()
    if scope is not None and course.get('teacher_id') != scope:
        return jsonify({"success": False, "message": "只能管理自己的课程"}), 403
    return None


def _attach_review_fields(rows, content_type):
    """给内容所有者的列表补上最近一次审核结论与驳回理由。"""
    latest = reviews_db.get_latest_reviews_by_content(
        content_type, [row['id'] for row in rows],
    )
    for row in rows:
        review = latest.get(row['id'])
        row['review_comment'] = (review or {}).get('review_comment') or ''
        row['reviewed_by'] = (review or {}).get('reviewed_by') or ''
        row['reviewed_at'] = (review or {}).get('reviewed_at') or ''
    return rows


# ==================== 通知公告 ====================

@teaching_support_bp.route('/api/teacher/announcements', methods=['GET'])
@require_capability('teaching.read', anonymous=401)
def get_announcements():
    announcements = teaching.get_announcements(teacher_id=_teacher_scope())
    return jsonify({"success": True, "announcements": announcements})


@teaching_support_bp.route('/api/teacher/announcements', methods=['POST'])
@require_capability('teaching.manage', anonymous=401)
def create_announcement():
    data = request.get_json()
    title = data.get('title', '')
    content = data.get('content', '')
    category = data.get('category', '通知')
    pinned = 1 if data.get('pinned') else 0
    if not title or not content:
        return jsonify({"success": False, "message": "请填写标题和内容"})
    user = get_session_user()
    scope = _teacher_scope(user)
    teacher_id = teaching.GLOBAL_TEACHER_ID if scope is None else scope
    aid = teaching.create_announcement(
        title, content, category, pinned, teacher_id=teacher_id,
    )
    # 自动给所有学员发通知
    notifications.create_notification_for_all_students(
        'announcement', f'新{category}', title, 'announcement', aid,
        teacher_id=None if scope is None else scope,
    )
    return jsonify({"success": True, "message": "发布成功", "id": aid})


@teaching_support_bp.route('/api/teacher/announcements/<int:ann_id>', methods=['DELETE'])
@require_capability('teaching.manage', anonymous=401)
def delete_announcement(ann_id):
    if teaching.delete_announcement(ann_id, teacher_id=_teacher_scope()):
        return jsonify({"success": True, "message": "删除成功"})
    return jsonify({"success": False, "message": "未找到通知"})


# ==================== 学员个人数据 ====================

# 2026-10-07：「发布作业」整块下架，`/api/student/submissions`（我的作业提交）
# 与它配套的教师侧 `/api/teacher/submissions/<id>` 一并删除 —— 前端零调用，
# 学员端的「我的作业」面板已在 v55 下架；三种实训的历史记录走 /api/ecommerce/*/records。


@teaching_support_bp.route('/api/student/announcements', methods=['GET'])
def get_my_announcements():
    """获取通知公告列表（学员可见）"""
    user = get_session_user()
    if not user or user.get('role') != STUDENT:
        return jsonify({"success": True, "announcements": []})
    teacher_id = students_db.get_teacher_id_for_student_account(
        user['username']
    )
    if not teacher_id:
        return jsonify({"success": True, "announcements": []})
    announcements = teaching.get_announcements(
        limit=30, teacher_id=teacher_id,
    )
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
@require_capability('teaching.manage', anonymous=401)
def grade_submission():
    data = request.get_json()
    submission_id = data.get('submission_id')
    score = data.get('score')
    feedback = data.get('feedback', '')
    if submission_id is None or score is None:
        return jsonify({"success": False, "message": "请填写批改信息"})
    # 取提交上下文以发送通知：学员是谁、这条提交挂在哪个作业上。
    # 走 v_submission_context（提交 JOIN 作业），域路由不自己写 SQL。
    sub = teaching.get_submission_context(submission_id)
    scope = _teacher_scope()
    if sub and scope is not None:
        owner = students_db.get_teacher_id_for_student_account(
            sub['student_id']
        )
        if owner != scope:
            return jsonify({
                "success": False,
                "message": "只能批改自己名册学员的提交",
            }), 403
    if teaching.grade_submission(submission_id, score, feedback):
        if sub:
            notifications.create_notification(sub['student_id'], 'grade', '实训已批改', f'得分：{score}', 'assignment', sub['assignment_id'])
        return jsonify({"success": True, "message": "批改成功"})
    return jsonify({"success": False, "message": "批改失败"})


@teaching_support_bp.route('/api/teacher/trainings', methods=['GET'])
@require_capability('teaching.read', anonymous=401)
def teacher_get_trainings():
    """教师端「实训提交」页：全部学员的电商实训提交（直播/文案/客服）。

    数据来自 assignment_submissions（学生端 /api/ecommerce/{live,copy,cs}/submit 写入）。
    批改仍走既有 /api/teacher/assignments/grade，会给学员发站内通知。
    """
    out = []
    for r in teaching.get_all_trainings(teacher_id=_teacher_scope()):
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
@require_capability('teaching.read', anonymous=401)
def get_analytics():
    data = teaching.get_analytics_data(teacher_id=_teacher_scope())
    return jsonify({"success": True, "analytics": data})


# ==================== 课程管理 ====================

@teaching_support_bp.route('/api/teacher/courses', methods=['GET'])
@require_capability('course.read')
def teacher_get_courses():
    course_list = courses_db.get_courses(
        teacher_id=_teacher_scope(), published_only=False,
    )
    return jsonify({
        "success": True,
        "courses": _attach_review_fields(course_list, 'course'),
    })


@teaching_support_bp.route('/api/teacher/courses', methods=['POST'])
@require_capability('course.manage')
def teacher_create_course():
    user = get_session_user()
    data = request.get_json()
    course_id = courses_db.create_course(
        data.get('title', ''), data.get('description', ''),
        data.get('category', ''), user['username'],
        data.get('cover_url', ''))
    return jsonify({"success": True, "id": course_id, "message": "课程创建成功，等待审核"})


@teaching_support_bp.route('/api/teacher/courses/<int:course_id>', methods=['PUT'])
@require_capability('course.manage')
def teacher_update_course(course_id):
    err = _course_owner_error(course_id)
    if err:
        return err
    data = request.get_json()
    courses_db.update_course(course_id, **{k: v for k, v in data.items()
        if k in ('title', 'description', 'category', 'cover_url')})
    return jsonify({"success": True, "message": "更新成功"})


@teaching_support_bp.route('/api/teacher/courses/<int:course_id>', methods=['DELETE'])
@require_capability('course.manage')
def teacher_delete_course(course_id):
    err = _course_owner_error(course_id)
    if err:
        return err
    courses_db.delete_course(course_id)
    return jsonify({"success": True, "message": "删除成功"})


# ==================== 课程素材 ====================

@teaching_support_bp.route('/api/teacher/courses/<int:course_id>/materials', methods=['GET'])
@require_capability('course.read')
def teacher_get_materials(course_id):
    err = _course_owner_error(course_id)
    if err:
        return err
    materials = courses_db.get_course_materials(course_id)
    return jsonify({"success": True, "materials": materials})


@teaching_support_bp.route('/api/teacher/courses/<int:course_id>/materials', methods=['POST'])
@require_capability('course.manage')
def teacher_add_material(course_id):
    err = _course_owner_error(course_id)
    if err:
        return err
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
    mat_id = courses_db.add_course_material(course_id, mtype, f.filename, filepath)
    return jsonify({"success": True, "id": mat_id, "message": "上传成功"})


@teaching_support_bp.route('/api/teacher/materials/<int:mat_id>', methods=['DELETE'])
@require_capability('course.manage')
def teacher_delete_material(mat_id):
    owner = courses_db.get_course_material_owner(mat_id)
    if owner is None:
        return jsonify({"success": False, "message": "素材不存在"}), 404
    scope = _teacher_scope()
    if scope is not None and owner != scope:
        return jsonify({"success": False, "message": "只能管理自己的课程素材"}), 403
    filepath = courses_db.delete_course_material(mat_id)
    if filepath:
        full = os.path.join(BASE_DIR, filepath)
        if os.path.exists(full):
            os.remove(full)
    return jsonify({"success": True, "message": "删除成功"})


# ==================== 3D 模型管理 ====================

@teaching_support_bp.route('/api/teacher/models-3d', methods=['GET'])
@require_capability('course.read', anonymous=401)
def teacher_get_models_3d():
    user = get_session_user()
    # 教师只看自己上传的；其他持 course.read 的角色看全部
    teacher_id = _teacher_scope(user)
    models = courses_db.get_models_3d(teacher_id=teacher_id,
                                    published_only=False)
    return jsonify({
        "success": True,
        "models": _attach_review_fields(models, 'model_3d'),
    })


@teaching_support_bp.route('/api/teacher/models-3d', methods=['POST'])
@require_capability('course.manage', anonymous=401)
def teacher_create_model_3d():
    user = get_session_user()
    if 'file' not in request.files:
        return jsonify({
            "success": False,
            "code": "empty_file",
            "message": "请选择模型文件",
        }), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({
            "success": False,
            "code": "empty_file",
            "message": "文件名为空",
        }), 400
    # 文件类型校验：仅允许常见 3D 模型格式
    ext = os.path.splitext(f.filename)[1].lower().lstrip('.')
    if ext not in _MODEL_3D_EXTS:
        return jsonify({
            "success": False,
            "code": "unsupported_format",
            "message": MODEL_3D_FORMAT_MESSAGE,
        }), 400
    title = request.form.get('title', f.filename)
    description = request.form.get('description', '')
    craft_type = request.form.get('craft_type', '')
    # 保存文件
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{f.filename}"
    filepath = os.path.join('uploads', 'models_3d', filename)
    os.makedirs(os.path.dirname(os.path.join(BASE_DIR, filepath)), exist_ok=True)
    save_full = os.path.join(BASE_DIR, filepath)
    f.save(save_full)
    # 记录真实文件大小（上限来自共享常量，超限删除并拒绝）
    file_size = os.path.getsize(save_full) if os.path.exists(save_full) else 0
    if file_size == 0:
        os.remove(save_full)
        return jsonify({
            "success": False,
            "code": "empty_file",
            "message": "文件为空，请重新选择",
        }), 400
    if file_size > _MODEL_3D_MAX_BYTES:
        if os.path.exists(save_full):
            os.remove(save_full)
        return jsonify({
            "success": False,
            "code": "file_too_large",
            "message": "文件过大，模型文件不能超过 %dMB" % MAX_UPLOAD_MEGABYTES,
        }), 400
    model_id = courses_db.create_model_3d(title, description, craft_type,
                                         filepath, f.filename, file_size, user['username'])
    return jsonify({"success": True, "id": model_id, "message": "3D模型上传成功，等待审核"})


@teaching_support_bp.route('/api/teacher/models-3d/<int:model_id>', methods=['DELETE'])
@require_capability('course.manage', anonymous=401)
def teacher_delete_model_3d(model_id):
    user = get_session_user()
    target = courses_db.get_model_3d_by_id(model_id)
    if not target:
        return jsonify({
            "success": False,
            "message": "模型不存在",
        }), 404
    scope = _teacher_scope(user)
    if scope is not None and target.get('teacher_id') != scope:
        return jsonify({
            "success": False,
            "message": "只能删除自己上传的模型",
        }), 403
    filepath = courses_db.delete_model_3d(model_id)
    if filepath:
        full = os.path.join(BASE_DIR, filepath)
        if os.path.exists(full):
            os.remove(full)
    return jsonify({"success": True, "message": "删除成功"})
