# -*- coding: utf-8 -*-
"""农业培训域的农事日历数据兜底。

farming_products 表读空时的回退目录与 AI 不可用时的静态建议。两者都是 T10
要删的内容常量（REFACTOR-PLAN 4.2），届时本模块随之消失，所以不往这里加新东西。

T06 已把 _month_in_phase 与 _farming_task_brief 两个纯函数移入
backend/db_domains/farming.py：它们服务的是农时内容，跟着数据走，读侧只认一处。
"""

import logging


# farming_products 表为空时的回退目录（与原硬编码一致，保证平滑过渡）
_DEFAULT_AGRICULTURE_PRODUCTS = [
    {"id": "lychee", "name": "荔枝", "icon": "apple-alt", "desc": "广东特色水果"},
    {"id": "longan", "name": "龙眼", "icon": "circle", "desc": "岭南佳果"},
    {"id": "aquatic", "name": "水产养殖", "icon": "fish", "desc": "鱼虾蟹贝"},
    {"id": "rice", "name": "水稻", "icon": "seedling", "desc": "主要粮食作物"},
    {"id": "tea", "name": "茶叶", "icon": "mug-hot", "desc": "广东名茶"},
    {"id": "vegetable", "name": "蔬菜", "icon": "carrot", "desc": "时令蔬菜"},
]

# 静态兜底建议：未配置密钥 / 上游失败 / 被限流时使用，保证建议栏始终可用
_STATIC_AGRI_SUGGESTIONS = {
    "lychee": ["荔枝花期如何管理？", "如何防治荔枝霜疫霉病？", "荔枝采后怎样恢复树势？", "荔枝膨大期施什么肥？"],
    "longan": ["龙眼如何疏花疏果？", "龙眼鬼帚病怎么防治？", "龙眼冬季管理要点？", "龙眼什么时候采收最好？"],
    "aquatic": ["鱼塘水质如何调节？", "虾塘增氧机怎么开？", "鱼病预防有哪些方法？", "养殖密度多少合适？"],
    "rice": ["水稻纹枯病怎么防治？", "水稻什么时候晒田好？", "稻飞虱用什么药？", "水稻收割最佳时期？"],
    "tea": ["茶园如何进行冬管？", "茶叶虫害绿色防控？", "春茶采摘标准是什么？", "茶树修剪技术要点？"],
    "vegetable": ["蔬菜大棚如何控温？", "叶菜类常见病害防治？", "有机蔬菜怎么施肥？", "蔬菜轮作有什么好处？"]
}

logger = logging.getLogger(__name__)


def _static_agri_suggestions(product):
    return list(_STATIC_AGRI_SUGGESTIONS.get(product, _STATIC_AGRI_SUGGESTIONS["lychee"]))


__all__ = [
    '_DEFAULT_AGRICULTURE_PRODUCTS', '_STATIC_AGRI_SUGGESTIONS',
    '_static_agri_suggestions',
]
