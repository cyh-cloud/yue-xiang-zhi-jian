# -*- coding: utf-8 -*-
"""公开域路由：首页统计、系统公告、公开课程、公开 3D 模型。

从 app.py 迁出（后端按领域拆分 T09），URL、请求响应结构、状态码、错误码保持不变。

四条路由全部对匿名访客开放：门户页（index.html / teacher.html / 各门户页）在未登录
状态下就要拿到 Hero 统计、公告、课程与 3D 模型。发布态的过滤由数据层按参数保证
（published_only / active_only），路由层不重复判断。

---- 首页统计（公开，真实库计数）----
P1-3：Hero 三个统计数字原为硬编码假数据（12000/86/3500），违反「不编造」红线。
改为读取数据库真实条数：服务农户=学员数、培训课程=课程数、就业对接=岗位数。
即便演示库稀疏也照实展示，绝不虚构。

---- 公开求购（用户端可见）：2026-10-06 随「供应链求购不做」整体下线 ----
学员端从未渲染过该接口（首页只有标题文案），此处一并移除，不留无界面的空接口。
"""

from flask import Blueprint, jsonify, request

import database

public_bp = Blueprint('public', __name__)


@public_bp.route('/api/home/stats', methods=['GET'])
def public_home_stats():
    conn = database.get_connection()
    try:
        farmers = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        courses = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        jobs = conn.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0]
    finally:
        conn.close()
    return jsonify({
        "success": True,
        "stats": {
            "farmers": farmers,
            "courses": courses,
            "jobs": jobs
        }
    })


@public_bp.route('/api/system-announcements', methods=['GET'])
def public_get_system_announcements():
    anns = database.get_system_announcements(active_only=True)
    return jsonify({"success": True, "announcements": anns})


@public_bp.route('/api/teacher/public-courses', methods=['GET'])
def public_get_courses():
    courses = database.get_courses(published_only=True)
    return jsonify({"success": True, "courses": courses})


@public_bp.route('/api/teacher/public-courses/<int:course_id>', methods=['GET'])
def public_get_course_detail(course_id):
    course = database.get_course(course_id)
    if not course:
        return jsonify({"success": False, "message": "课程不存在"}), 404
    materials = database.get_course_materials(course_id)
    return jsonify({"success": True, "course": course, "materials": materials})


@public_bp.route('/api/teacher/public-models-3d', methods=['GET'])
def public_get_models_3d():
    craft_type = request.args.get('craft_type', '')
    models = database.get_models_3d(published_only=True)
    if craft_type:
        models = [m for m in models if m.get('craft_type') == craft_type]
    return jsonify({"success": True, "models": models})
