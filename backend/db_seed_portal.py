#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门户与社区展示内容的播种：首页轮播、系统公告、讨论区热帖。

三者都是「全新库里放几条能看的内容」，只在空库时灌一次，既有库一律不碰
（运营改过的内容不能被种子逻辑重置）。拆自 database.py 的 _seed_data()。
"""

def seed_portal_content(cursor):
    """全新库：灌入首页轮播、系统公告与讨论区热帖。"""
    # 轮播图种子数据
    carousels = [
        ("粤乡智匠正式上线", "https://placehold.co/1200x400/10b981/white?text=粤乡智匠", "", 0),
        ("乡村振兴政策解读", "https://placehold.co/1200x400/00b4d8/white?text=政策解读", "/resources", 1),
        ("非遗技艺传承计划", "https://placehold.co/1200x400/8b5cf6/white?text=非遗传承", "/crafts", 2),
    ]
    for title, img, link, sort in carousels:
        cursor.execute("INSERT INTO carousels (title, image_url, link_url, sort_order) VALUES (?, ?, ?, ?)",
                       (title, img, link, sort))

    # 系统公告种子数据
    cursor.execute("INSERT INTO system_announcements (title, content, is_pinned, created_by) VALUES (?, ?, ?, ?)",
                   ('欢迎使用粤乡智匠平台', '粤乡智匠是基于AI实训系统的农村本土人才赋能平台，致力于为广东乡村振兴培养实用型人才。', 1, 'admin_demo'))

    # 讨论区种子数据
    cursor.execute("INSERT INTO discussions (title, content, category, user_id) VALUES (?, ?, ?, ?)",
                   ('荔枝种植经验交流', '各位种植荔枝的老乡，今年荔枝花期管理有什么心得？欢迎分享！', 'agriculture', 'student_demo'))
    cursor.execute("INSERT INTO discussions (title, content, category, user_id) VALUES (?, ?, ?, ?)",
                   ('电商直播新手问答', '刚开始做直播带货，想请教各位前辈有什么注意事项？', 'ecommerce', 'student_demo'))


def seed_carousels(cursor):
    """已有数据库时，补充默认轮播图"""
    carousels = [
        ("粤乡智匠正式上线", "https://placehold.co/1200x400/10b981/white?text=粤乡智匠", "", 0),
        ("乡村振兴政策解读", "https://placehold.co/1200x400/00b4d8/white?text=政策解读", "/resources", 1),
        ("非遗技艺传承计划", "https://placehold.co/1200x400/8b5cf6/white?text=非遗传承", "/crafts", 2),
    ]
    for title, img, link, sort in carousels:
        cursor.execute("INSERT INTO carousels (title, image_url, link_url, sort_order) VALUES (?, ?, ?, ?)",
                       (title, img, link, sort))
