# -*- coding: utf-8 -*-
"""教师管理域路由：名册与学员的增删改查、账号绑定。

从 app.py 迁出（后端按领域拆分 T16），URL、请求响应结构、状态码、错误码保持不变。

与教学支撑域（domains.teaching_support）的分界按 spec 的「切分单位」一节：
本域管「教师手下的学员是谁」这一侧（名册行、学员详情、关联/新建平台账号），
课程、材料、公告、批改、学情分析属教学支撑域。两者共用 `/api/teacher/*` 前缀但
分属不同领域，因此是两个蓝图对象。

一个领域一个蓝图（docs/adr/0001），蓝图对象 teacher_bp 定义在本文件。

跨域边界：

- 会话取用户与角色装饰器只用共享层 core.session（require_role / get_session_user），
  教师端接口统一要求 TEACHER_ROLES（teacher + super_admin）；
- 数据访问一律走 database 契约层（db_domains/students.py、db_domains/users.py）；
- AI 调用走共享层 ai.client，且按模块属性调用（见 domains/teacher/reports.py）。
"""

import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

from core.session import TEACHER_ROLES, require_role
import database

from domains.teacher.reports import _build_fallback_overview, _build_fallback_report, generate_report

logger = logging.getLogger(__name__)

teacher_bp = Blueprint('teacher', __name__)


@teacher_bp.route('/api/teacher/dashboard', methods=['GET'])
@require_role(*TEACHER_ROLES)
def get_teacher_dashboard():
    # 2026-10-07：原返回里有一段硬编码的 recent_activities（"张小明 2小时前" 等
    # 编造数据），前端从未渲染它。按「不编造」红线直接移除，只回真实统计。
    stats = database.get_dashboard_stats()
    return jsonify({"success": True, "dashboard": {"stats": stats}})


@teacher_bp.route('/api/teacher/students', methods=['GET'])
@require_role(*TEACHER_ROLES)
def get_students():
    search = request.args.get('search', None)
    students = database.get_students(search)
    # 附上「证书真实完成度」—— 名册自己的 progress 是手填字段，学员端没有任何入口
    # 会更新它；前端「已获得证书」的判定改用真实证书数据（2026-10-07）。
    comp = {r['id']: r for r in database.get_roster_completion()}
    for s in students:
        r = comp.get(s['id'])
        if r:
            s['cert_total'] = r['cert_total']
            s['cert_earned'] = r['cert_earned']
            s['completion'] = r['completion']
            s['has_cert_data'] = r['has_cert_data']
    return jsonify({"success": True, "students": students})


@teacher_bp.route('/api/teacher/students/<student_id>', methods=['GET'])
@require_role(*TEACHER_ROLES)
def get_student_detail(student_id):
    """获取学员详情（附证书真实完成度）"""
    student = database.get_student(student_id)
    if student:
        for r in database.get_roster_completion():
            if r['id'] == student_id:
                student.update({
                    'cert_total': r['cert_total'], 'cert_earned': r['cert_earned'],
                    'completion': r['completion'], 'has_cert_data': r['has_cert_data'],
                })
                break
        return jsonify({"success": True, "student": student})
    return jsonify({"success": False, "message": "未找到学员"})


@teacher_bp.route('/api/teacher/students/add', methods=['POST'])
@require_role(*TEACHER_ROLES)
def add_student():
    """添加学员（名册行），并可选「关联已有账号」或「新建账号」。

    2026-10-07 用户拍板：名册与账号长期是两套数据，新加的学员登不进来、
    收不到通知、证书也进不了统计。现在添加时可以在三种模式里选一种：
      · link_username  —— 关联一个尚未被占用的学员账号；
      · new_username + new_password —— 直接为该学员新建平台账号并关联；
      · 都不传        —— 只建名册（接口会在 message 里明确提示「无法登录」）。
    失败时不留半成品：账号建好但关联失败，会把刚插入的名册行删掉。
    """
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    class_name = data.get('class_name', '')
    direction = data.get('direction', '')
    link_username = (data.get('link_username') or '').strip()
    new_username = (data.get('new_username') or '').strip()
    new_password = (data.get('new_password') or '').strip()

    if not name:
        return jsonify({"success": False, "message": "请输入学员姓名"}), 400

    account_username = ''
    if new_username:
        if len(new_password) < 6:
            return jsonify({"success": False, "message": "初始密码至少 6 位"}), 400
        uid, msg = database.register_user(new_username, new_password, name, 'student')
        if not uid:
            return jsonify({"success": False, "message": f"账号创建失败：{msg}"}), 400
        account_username = uid
    elif link_username:
        account_username = link_username

    sid = database.add_student(name, class_name, direction)
    if account_username:
        ok, msg = database.set_student_account(sid, account_username)
        if not ok:
            # 关联失败（账号不存在 / 已被别人占用…）→ 回滚名册行，避免留下孤儿记录
            database.delete_student(sid)
            return jsonify({"success": False, "message": msg}), 400
        tail = (f'已新建并关联账号 {account_username}' if new_username
                else f'已关联账号 {account_username}')
    else:
        tail = '尚未关联平台账号，该学员暂时无法登录、收不到站内通知'

    return jsonify({"success": True, "message": f"添加成功，学员编号：{sid}；{tail}",
                    "student_id": sid, "linked_account": account_username})


@teacher_bp.route('/api/teacher/linkable-accounts', methods=['GET'])
@require_role(*TEACHER_ROLES)
def get_linkable_accounts():
    """可供名册关联的学员账号（role=student 且未被占用）。"""
    return jsonify({"success": True, "accounts": database.get_linkable_student_accounts()})


@teacher_bp.route('/api/teacher/students/<student_id>/link', methods=['POST'])
@require_role(*TEACHER_ROLES)
def link_student_account(student_id):
    """关联 / 解除名册与平台账号。body: {"username": "xxx"}，空串表示解除。"""
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    ok, msg = database.set_student_account(student_id, username)
    if not ok:
        return jsonify({"success": False, "message": msg}), 400
    return jsonify({"success": True, "message": msg, "user_id": username})


@teacher_bp.route('/api/teacher/students/<student_id>', methods=['PUT'])
@require_role(*TEACHER_ROLES)
def update_student(student_id):
    """编辑学员"""
    data = request.get_json()
    result = database.update_student(
        student_id,
        name=data.get('name'),
        class_name=data.get('class_name'),
        direction=data.get('direction'),
        progress=data.get('progress'),
        status=data.get('status')
    )
    if result:
        return jsonify({"success": True, "message": "更新成功"})
    return jsonify({"success": False, "message": "未找到学员"})


@teacher_bp.route('/api/teacher/students/<student_id>', methods=['DELETE'])
@require_role(*TEACHER_ROLES)
def delete_student(student_id):
    """删除学员"""
    result = database.delete_student(student_id)
    if result:
        return jsonify({"success": True, "message": "删除成功"})
    return jsonify({"success": False, "message": "未找到学员"})


@teacher_bp.route('/api/teacher/reports/generate', methods=['POST'])
@require_role(*TEACHER_ROLES)
def generate_teacher_report():
    """AI生成教学报告 — 接受自然语言prompt，灵活生成"""
    data = request.get_json()
    user_prompt = data.get('prompt', '').strip()
    if not user_prompt:
        return jsonify({"success": False, "message": "请输入分析需求"}), 400

    try:
        # 2026-10-07：改用「证书真实完成度」口径（get_roster_completion）。
        # 原 context 直接聚合 students.progress —— 那是**手填**字段，学员端没有任何
        # 入口会更新它，AI 据此写出的「学员进度」与真实学习情况无关。
        roster = database.get_roster_completion()
        if not roster:
            return jsonify({"success": True, "report": {
                "title": "AI 教学报告",
                "generated_at": datetime.now().isoformat(),
                "content": "## 暂无数据\n\n当前没有学员数据，请先添加学员后再生成报告。"
            }})

        report = generate_report(roster, user_prompt)
        return jsonify({"success": True, "report": {
            "title": "AI 教学报告",
            "generated_at": datetime.now().isoformat(),
            "content": report["content"],
            "overview": report["overview"]
        }})

    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        # 兜底报告（口径与主路径一致：证书真实完成度）
        try:
            roster = database.get_roster_completion()
            fallback = _build_fallback_report(roster, user_prompt)
            overview = _build_fallback_overview(roster, user_prompt)
        except Exception:
            fallback = "## 生成失败\n\nAI 服务暂时不可用，请稍后重试。"
            overview = None
        resp = {"success": True, "report": {
            "title": "AI 教学报告",
            "generated_at": datetime.now().isoformat(),
            "content": fallback
        }}
        if overview:
            resp["report"]["overview"] = overview
        return jsonify(resp)