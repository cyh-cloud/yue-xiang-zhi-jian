# -*- coding: utf-8 -*-
"""运营域：手工技艺的内容维护路由（T15）。

覆盖五层内容：技艺（crafts）、步骤（craft_steps）、采购分类
（craft_purchase_categories）、采购条目（craft_purchase_items）与预算
（craft_budgets）。全部挂在 /api/operator/crafts/ 下。

与前台的口径关系：前台 /api/crafts/list 与 /api/crafts/<id> 是这些表的只读
视图，两边读同一个库，所以「运营改完前台立即返回新值」不需要任何同步步骤。

数据形状是这张票的主要风险：库里采购指南是**四张平表**，前台要的是三层嵌套

    purchase_guide.categories[].items[]   与   purchase_guide.budget

写侧不自己拼这个形状，而是按平表收口：分类一条、条目一条、预算一条。
读侧的 get_craft_detail() 负责按 sort_order 组装回嵌套形状，所以后台只要保证
「sort_order 写得对」，形状自然回来。这也是为什么不提供「整门技艺一次 POST
覆盖」的接口：那要把三层嵌套拆散的逻辑在路由层再写一遍，而组装规则已经在
数据层有一份了（见 db_domains.crafts._purchase_guide）。

两条口径：

1. craft_steps 与 craft_purchase_items 在库里没有显式主键（schema 里只有
   外键），后台用 rowid 定位单行。表不是 WITHOUT ROWID，rowid 稳定可用；
2. 采购条目必须挂在一个已存在的分类下，否则读侧分组时它会掉出
   items.get(c['key'], []) 的兜底，学员端看不到这条物品，
   而运营以为自己写进去了。
"""

from flask import request

from core.permissions import require_capability
from db_domains import crafts as crafts_db
from domains.operator.routes import json_body, ok, fail, run_write

# 运营域读 craft 能力域，写侧与 craft.manage 对应（声明供机械检查判权）。
CAPABILITIES_USED = ('craft.content.manage',)

_MAX_TEXT = 500
_MAX_TITLE = 60

# 视频教学的入参分成两类：文本列与整数列（时长 / 播放 / 弹幕 / 点赞 / 发布日）。
# sort_order 也在这里，它决定详情里 videos 的顺序。
_VIDEO_TEXT_FIELDS = ('bvid', 'title', 'author', 'cover')
_VIDEO_INT_FIELDS = ('duration', 'view_count', 'danmaku', 'like_count',
                     'pubdate', 'sort_order')


def _text(value, limit=_MAX_TEXT):
    if value is None:
        return ''
    text = value if isinstance(value, str) else str(value)
    return text.strip()[:limit]


def _optional_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _fields(data, keys):
    """取一组文本字段。只在键出现时收，PUT 因此能做局部更新。"""
    return {key: _text(data.get(key)) for key in keys if key in data}


def register_crafts_routes(bp):
    """把手工技艺的维护路由挂到蓝图。"""

    # ---- 技艺 ----

    @bp.route('/api/operator/crafts', methods=['GET'])
    @require_capability('craft.content.manage')
    def operator_crafts():
        """技艺列表，带步骤数与采购条目数，供后台判断「这门技艺填全了没有」。"""
        crafts = []
        for summary in crafts_db.get_crafts():
            craft = crafts_db.get_craft_row(summary['id']) or dict(summary)
            craft['step_count'] = len(crafts_db.get_craft_steps(craft['id']))
            craft['item_count'] = len(
                crafts_db.get_craft_purchase_items(craft['id']))
            craft['has_budget'] = crafts_db.get_craft_budget(craft['id']) is not None
            crafts.append(craft)
        return ok(crafts=crafts)

    @bp.route('/api/operator/crafts', methods=['POST'])
    @require_capability('craft.content.manage')
    def operator_craft_create():
        data = json_body()
        craft_id = _text(data.get('id'))
        name = _text(data.get('name'), _MAX_TITLE)
        if not craft_id:
            return fail(u'技艺 id 不能为空', 400)
        if not name:
            return fail(u'技艺名称不能为空', 400)
        fields = _fields(data, ('name', 'origin', 'history', 'level'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        # name 已在必填校验里取过，从 fields 里摘掉，否则同一个键会按位置
        # 与关键字各传一次（create_craft(craft_id, name, **fields)）。
        fields.pop('name', None)
        return run_write(crafts_db.create_craft, craft_id, name, **fields)

    @bp.route('/api/operator/crafts/<craft_id>', methods=['PUT'])
    @require_capability('craft.content.manage')
    def operator_craft_update(craft_id):
        data = json_body()
        fields = _fields(data, ('name', 'origin', 'history', 'level'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(crafts_db.update_craft, craft_id, **fields)

    @bp.route('/api/operator/crafts/<craft_id>', methods=['DELETE'])
    @require_capability('craft.content.manage')
    def operator_craft_delete(craft_id):
        return run_write(crafts_db.delete_craft, craft_id)

    # ---- 步骤 ----

    @bp.route('/api/operator/crafts/<craft_id>/steps', methods=['GET'])
    @require_capability('craft.content.manage')
    def operator_craft_steps(craft_id):
        return ok(steps=crafts_db.get_craft_steps(craft_id))

    @bp.route('/api/operator/crafts/<craft_id>/steps', methods=['POST'])
    @require_capability('craft.content.manage')
    def operator_craft_step_create(craft_id):
        data = json_body()
        title = _text(data.get('title'), _MAX_TITLE)
        if not title:
            return fail(u'步骤标题不能为空', 400)
        fields = _fields(data, ('title', 'desc', 'tips'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        fields.pop('title', None)
        return run_write(crafts_db.create_craft_step, craft_id, title, **fields)

    @bp.route('/api/operator/crafts/steps/<int:step_id>', methods=['PUT'])
    @require_capability('craft.content.manage')
    def operator_craft_step_update(step_id):
        data = json_body()
        fields = _fields(data, ('title', 'desc', 'tips'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(crafts_db.update_craft_step, step_id, **fields)

    @bp.route('/api/operator/crafts/steps/<int:step_id>', methods=['DELETE'])
    @require_capability('craft.content.manage')
    def operator_craft_step_delete(step_id):
        return run_write(crafts_db.delete_craft_step, step_id)

    # ---- 采购指南：分类 ----

    @bp.route('/api/operator/crafts/<craft_id>/purchase-categories',
              methods=['GET'])
    @require_capability('craft.content.manage')
    def operator_craft_purchase_categories(craft_id):
        return ok(categories=crafts_db.get_craft_purchase_categories(craft_id))

    @bp.route('/api/operator/crafts/<craft_id>/purchase-categories',
              methods=['POST'])
    @require_capability('craft.content.manage')
    def operator_craft_purchase_category_create(craft_id):
        data = json_body()
        key = _text(data.get('key'), _MAX_TITLE)
        if not key:
            return fail(u'分类 key 不能为空', 400)
        fields = _fields(data, ('label', 'desc'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(crafts_db.create_craft_purchase_category,
                         craft_id, key, **fields)

    @bp.route('/api/operator/crafts/<craft_id>/purchase-categories/<key>',
              methods=['PUT'])
    @require_capability('craft.content.manage')
    def operator_craft_purchase_category_update(craft_id, key):
        data = json_body()
        fields = _fields(data, ('label', 'desc'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(crafts_db.update_craft_purchase_category,
                         craft_id, key, **fields)

    @bp.route('/api/operator/crafts/<craft_id>/purchase-categories/<key>',
              methods=['DELETE'])
    @require_capability('craft.content.manage')
    def operator_craft_purchase_category_delete(craft_id, key):
        return run_write(crafts_db.delete_craft_purchase_category, craft_id, key)

    # ---- 采购指南：条目 ----

    @bp.route('/api/operator/crafts/<craft_id>/purchase-items', methods=['GET'])
    @require_capability('craft.content.manage')
    def operator_craft_purchase_items(craft_id):
        category_key = _text(request.args.get('category_key'))
        return ok(items=crafts_db.get_craft_purchase_items(
            craft_id, category_key or None))

    @bp.route('/api/operator/crafts/<craft_id>/purchase-items', methods=['POST'])
    @require_capability('craft.content.manage')
    def operator_craft_purchase_item_create(craft_id):
        data = json_body()
        category_key = _text(data.get('category_key'), _MAX_TITLE)
        name = _text(data.get('name'), _MAX_TITLE)
        if not category_key:
            return fail(u'请选择采购分类', 400)
        if not name:
            return fail(u'物品名称不能为空', 400)
        fields = _fields(data, ('name', 'price', 'spec', 'tip', 'where'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        fields.pop('name', None)
        return run_write(crafts_db.create_craft_purchase_item,
                         craft_id, category_key, name, **fields)

    @bp.route('/api/operator/crafts/purchase-items/<int:item_id>',
              methods=['PUT'])
    @require_capability('craft.content.manage')
    def operator_craft_purchase_item_update(item_id):
        data = json_body()
        fields = _fields(data, ('name', 'price', 'spec', 'tip', 'where'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(crafts_db.update_craft_purchase_item, item_id, **fields)

    @bp.route('/api/operator/crafts/purchase-items/<int:item_id>',
              methods=['DELETE'])
    @require_capability('craft.content.manage')
    def operator_craft_purchase_item_delete(item_id):
        return run_write(crafts_db.delete_craft_purchase_item, item_id)

    # ---- 采购指南：预算 ----

    @bp.route('/api/operator/crafts/<craft_id>/budget', methods=['GET'])
    @require_capability('craft.content.manage')
    def operator_craft_budget(craft_id):
        budget = crafts_db.get_craft_budget(craft_id)
        if budget is None:
            return fail(u'这门技艺还没有填采购预算', 404)
        return ok(budget=budget)

    @bp.route('/api/operator/crafts/<craft_id>/budget', methods=['PUT'])
    @require_capability('craft.content.manage')
    def operator_craft_budget_update(craft_id):
        """预算一门技艺一行，PUT 即「写入 / 覆盖」，没有 POST 与 DELETE。

        与 pest 的实拍图关联同一个形状（INSERT OR REPLACE，主键冲突即覆盖）：
        「先删再建」会让中途失败留下空预算，而前台 purchase_guide['budget']
        缺了就整块不渲染。
        """
        data = json_body()
        fields = _fields(data, ('starter', 'advanced', 'buying_tips'))
        return run_write(crafts_db.set_craft_budget, craft_id, **fields)

    # ---- 视频教学 ----

    @bp.route('/api/operator/crafts/<craft_id>/videos', methods=['GET'])
    @require_capability('craft.content.manage')
    def operator_craft_videos(craft_id):
        return ok(videos=crafts_db.get_craft_videos_for_editor(craft_id))

    @bp.route('/api/operator/crafts/<craft_id>/videos', methods=['POST'])
    @require_capability('craft.content.manage')
    def operator_craft_video_create(craft_id):
        data = json_body()
        bvid = _text(data.get('bvid'), _MAX_TITLE)
        if not bvid:
            return fail(u'视频 bvid 不能为空', 400)
        fields = _fields(data, _VIDEO_TEXT_FIELDS)
        for key in _VIDEO_INT_FIELDS:
            if key in data:
                fields[key] = _optional_int(data.get(key)) or 0
        fields.pop('bvid', None)
        return run_write(crafts_db.create_craft_video, craft_id, bvid, **fields)

    @bp.route('/api/operator/crafts/videos/<int:video_id>', methods=['PUT'])
    @require_capability('craft.content.manage')
    def operator_craft_video_update(video_id):
        data = json_body()
        fields = _fields(data, _VIDEO_TEXT_FIELDS)
        for key in _VIDEO_INT_FIELDS:
            if key in data:
                fields[key] = _optional_int(data.get(key)) or 0
        return run_write(crafts_db.update_craft_video, video_id, **fields)

    @bp.route('/api/operator/crafts/videos/<int:video_id>', methods=['DELETE'])
    @require_capability('craft.content.manage')
    def operator_craft_video_delete(video_id):
        return run_write(crafts_db.delete_craft_video, video_id)


OPERATOR_CRAFTS_ROUTES = (
    ('/api/operator/crafts', 'GET'),
    ('/api/operator/crafts', 'POST'),
    ('/api/operator/crafts/<craft_id>', 'PUT'),
    ('/api/operator/crafts/<craft_id>', 'DELETE'),
    ('/api/operator/crafts/<craft_id>/steps', 'GET'),
    ('/api/operator/crafts/<craft_id>/steps', 'POST'),
    ('/api/operator/crafts/steps/<int:step_id>', 'PUT'),
    ('/api/operator/crafts/steps/<int:step_id>', 'DELETE'),
    ('/api/operator/crafts/<craft_id>/purchase-categories', 'GET'),
    ('/api/operator/crafts/<craft_id>/purchase-categories', 'POST'),
    ('/api/operator/crafts/<craft_id>/purchase-categories/<key>', 'PUT'),
    ('/api/operator/crafts/<craft_id>/purchase-categories/<key>', 'DELETE'),
    ('/api/operator/crafts/<craft_id>/purchase-items', 'GET'),
    ('/api/operator/crafts/<craft_id>/purchase-items', 'POST'),
    ('/api/operator/crafts/purchase-items/<int:item_id>', 'PUT'),
    ('/api/operator/crafts/purchase-items/<int:item_id>', 'DELETE'),
    ('/api/operator/crafts/<craft_id>/budget', 'GET'),
    ('/api/operator/crafts/<craft_id>/budget', 'PUT'),
    ('/api/operator/crafts/<craft_id>/videos', 'GET'),
    ('/api/operator/crafts/<craft_id>/videos', 'POST'),
    ('/api/operator/crafts/videos/<int:video_id>', 'PUT'),
    ('/api/operator/crafts/videos/<int:video_id>', 'DELETE'),
)

__all__ = ['register_crafts_routes', 'OPERATOR_CRAFTS_ROUTES', 'CAPABILITIES_USED']
