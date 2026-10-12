# -*- coding: utf-8 -*-
"""农业培训域的农事日历数据兜底与两个纯函数。

farming_products 表读空时的回退目录、物候期命中判定、提醒文案用的一行摘要。
它们只服务 calendar.py 的两条日历/提醒路径，没有第二个消费方，因此单独成模块、
不摊在路由文件里（路由文件有 600 行上限，见 spec 的验收门槛）。
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


def _month_in_phase(month, start_month, end_month):
    """物候期命中判定。start_month > end_month 表示跨年区间（如 11月 → 次年1月）。"""
    if start_month <= end_month:
        return start_month <= month <= end_month
    return month >= start_month or month <= end_month


def _farming_task_brief(task):
    """把任务压成「05日 花前病虫害预防」的一行摘要，供提醒文案使用。"""
    md = (task.get('task_md') or '')
    day = None
    if '-' in md:
        try:
            day = int(md.split('-', 1)[1])
        except (ValueError, IndexError):
            day = None
    return ('%d日 %s' % (day, task.get('title', ''))) if day else task.get('title', '')


__all__ = [
    '_DEFAULT_AGRICULTURE_PRODUCTS', '_STATIC_AGRI_SUGGESTIONS',
    '_static_agri_suggestions', '_month_in_phase', '_farming_task_brief',
]
