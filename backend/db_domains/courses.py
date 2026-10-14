#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""课程域：课程、课程素材与 3D 模型的读写删。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

from db_connection import get_connection

# 本模块的数据归属这个能力域。机械检查（tools/check_architecture.py）与
# backend/core/permissions.py 的 CAPABILITIES 都以此为准：谁 import 本模块，
# 谁就必须持 ${cap}.manage（读操作受 ${cap}.read 管）。
CAPABILITY = 'course'


def count_courses_and_models():
    """课程域窄接口：(3D 模型数, 课程数)。"""
    conn = get_connection()
    models = conn.execute("SELECT COUNT(*) FROM models_3d").fetchone()[0]
    courses_total = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    conn.close()
    return models, courses_total


def set_course_review_status(course_id, review_status):
    """课程域的审核窄接口：只改 courses 自己的 review_status 与 is_published。

    由审核域的 set_review_status() 按内容类型分派调用。is_published 与
    review_status 联动：只有 approved 才公开发布，其余状态一律下架，
    这样「驳回」与「撤销」不需要各自的写路径。
    """
    published = 1 if review_status == 'approved' else 0
    conn = get_connection()
    conn.execute("UPDATE courses SET review_status=?, is_published=? WHERE id=?",
                 (review_status, published, course_id))
    conn.commit()
    conn.close()


def set_model_3d_review_status(model_id, review_status):
    """3D 模型域的审核窄接口，与课程同构：approved 才公开发布。"""
    published = 1 if review_status == 'approved' else 0
    conn = get_connection()
    conn.execute("UPDATE models_3d SET review_status=?, is_published=? WHERE id=?",
                 (review_status, published, model_id))
    conn.commit()
    conn.close()


def create_course(title, description, category, teacher_id, cover_url=''):
    """教师创建课程"""
    # 延迟导入：审核域反过来要按内容类型分派到本模块，顶层导入会成环。
    from db_domains.reviews import create_content_review
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO courses (title, description, category, teacher_id, cover_url) VALUES (?, ?, ?, ?, ?)",
        (title, description, category, teacher_id, cover_url))
    conn.commit()
    course_id = cursor.lastrowid
    conn.close()
    # 创建审核记录
    create_content_review('course', course_id, teacher_id)
    return course_id

def get_courses(teacher_id=None, published_only=True):
    """获取课程列表"""
    conn = get_connection()
    query = "SELECT * FROM courses WHERE 1=1"
    params = []
    if teacher_id:
        query += " AND teacher_id = ?"
        params.append(teacher_id)
    if published_only:
        query += " AND is_published = 1"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_course(course_id):
    """获取单个课程"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_course(course_id, **kwargs):
    """更新课程"""
    conn = get_connection()
    allowed = {'title', 'description', 'category', 'cover_url'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if updates:
        set_clause = ', '.join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [course_id]
        conn.execute(f"UPDATE courses SET {set_clause} WHERE id=?", params)
        conn.commit()
    conn.close()
    return True

def delete_course(course_id):
    """删除课程及关联素材"""
    conn = get_connection()
    conn.execute("DELETE FROM course_materials WHERE course_id = ?", (course_id,))
    conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn.execute("DELETE FROM content_reviews WHERE content_type='course' AND content_id=?", (course_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 课程素材 ====================

def add_course_material(course_id, material_type, file_name, file_path, file_size=0):
    """添加课程素材"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO course_materials (course_id, material_type, file_name, file_path, file_size) VALUES (?, ?, ?, ?, ?)",
        (course_id, material_type, file_name, file_path, file_size))
    conn.commit()
    mat_id = cursor.lastrowid
    conn.close()
    return mat_id

def get_course_materials(course_id):
    """获取课程素材列表"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM course_materials WHERE course_id = ? ORDER BY sort_order", (course_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_course_material(mat_id):
    """删除课程素材"""
    conn = get_connection()
    row = conn.execute("SELECT file_path FROM course_materials WHERE id = ?", (mat_id,)).fetchone()
    conn.execute("DELETE FROM course_materials WHERE id = ?", (mat_id,))
    conn.commit()
    conn.close()
    return row['file_path'] if row else None


# ==================== 3D 模型 ====================

def create_model_3d(title, description, craft_type, file_path, file_name, file_size, teacher_id, thumbnail_url=''):
    """上传3D模型"""
    from db_domains.reviews import create_content_review
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO models_3d (title, description, craft_type, file_path, file_name, file_size, thumbnail_url, teacher_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, description, craft_type, file_path, file_name, file_size, thumbnail_url, teacher_id))
    conn.commit()
    model_id = cursor.lastrowid
    conn.close()
    create_content_review('model_3d', model_id, teacher_id)
    return model_id

def get_models_3d(teacher_id=None, published_only=True):
    """获取3D模型列表"""
    conn = get_connection()
    query = "SELECT * FROM models_3d WHERE 1=1"
    params = []
    if teacher_id:
        query += " AND teacher_id = ?"
        params.append(teacher_id)
    if published_only:
        query += " AND is_published = 1"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_model_3d(model_id):
    """删除3D模型"""
    conn = get_connection()
    row = conn.execute("SELECT file_path FROM models_3d WHERE id = ?", (model_id,)).fetchone()
    conn.execute("DELETE FROM models_3d WHERE id = ?", (model_id,))
    conn.execute("DELETE FROM content_reviews WHERE content_type='model_3d' AND content_id=?", (model_id,))
    conn.commit()
    conn.close()
    return row['file_path'] if row else None


# ==================== 评论 ====================
