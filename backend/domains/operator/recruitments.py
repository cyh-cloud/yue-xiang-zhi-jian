# -*- coding: utf-8 -*-
"""运营域：招募公告的内容维护路由（T15）。

覆盖两层内容：公告（recruitments）与公告来源（recruitment_sources）。
全部挂在 /api/operator/recruitments/ 下。

与前台的口径关系：前台 /api/employment/jobs 的 recruitments 数组是这两张表的
只读视图，两边读同一个库，所以「运营改完前台立即返回新值」不需要任何同步步骤。

⚠️ status / status_label / days_left / starts_in **不是可编辑字段**：它们在
库里没有列，是读侧按当天日期从 signup_start / deadline 现算的
（db_domains.recruitments._with_status）。运营要改报名状态，改起止日期；
前台要的四个派生值会自己跟上。写侧也不接收这四个键 —— 收下来没处存，
只会让运营以为改成功了。

公告不带审核门禁（不像课程 / 岗位 / 案例），所以这里没有 review_status，
也不需要 reviews 域参与。
"""

from core.permissions import require_capability
from db_domains import recruitments as recruitments_db
from domains.operator.routes import json_body, ok, fail, run_write

# 运营域读 recruit 能力域，写侧与 recruit.manage 对应（声明供机械检查判权）。
CAPABILITIES_USED = ('recruit.manage',)

_MAX_TEXT = 500
_MAX_TITLE = 60

# 岗位类别白名单。前台就业页的分类筛选项只认这几个
# （recruitments.RECRUIT_CATEGORIES，见 employment/routes.py 的 category_options），
# 写一个表外的值会出现「筛了永远是 0 条」的死筛选项。
_CATEGORIES = recruitments_db.RECRUIT_CATEGORIES


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


def register_recruitments_routes(bp):
    """把招募公告的维护路由挂到蓝图。"""

    # ---- 公告 ----

    @bp.route('/api/operator/recruitments', methods=['GET'])
    @require_capability('recruit.manage')
    def operator_recruitments():
        """公告列表，带上来源条数，供后台判断「这条公告填全了没有」。"""
        recruitments = []
        for row in recruitments_db.get_recruitment_rows():
            item = dict(row)
            item['source_count'] = len(
                recruitments_db.get_recruitment_sources(item['key']))
            recruitments.append(item)
        return ok(recruitments=recruitments)

    @bp.route('/api/operator/recruitments', methods=['POST'])
    @require_capability('recruit.manage')
    def operator_recruitment_create():
        data = json_body()
        key = _text(data.get('key'))
        title = _text(data.get('title'), _MAX_TITLE)
        if not key:
            return fail(u'公告 key 不能为空', 400)
        if not title:
            return fail(u'公告标题不能为空', 400)
        fields = _fields(data, ('title', 'org', 'region', 'category', 'job_type',
                                'headcount', 'education', 'experience', 'salary',
                                'description', 'signup_way', 'contact'))
        for column in ('publish_date', 'signup_start', 'deadline'):
            if column in data:
                fields[column] = _text(data.get(column), 10)
        if fields.get('category') and fields['category'] not in _CATEGORIES:
            return fail(u'岗位类别不在可选范围内', 400)
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        fields.pop('title', None)
        return run_write(recruitments_db.create_recruitment, key, title, **fields)

    @bp.route('/api/operator/recruitments/<key>', methods=['PUT'])
    @require_capability('recruit.manage')
    def operator_recruitment_update(key):
        data = json_body()
        fields = _fields(data, ('title', 'org', 'region', 'category', 'job_type',
                                'headcount', 'education', 'experience', 'salary',
                                'description', 'signup_way', 'contact'))
        for column in ('publish_date', 'signup_start', 'deadline'):
            if column in data:
                fields[column] = _text(data.get(column), 10)
        if fields.get('category') and fields['category'] not in _CATEGORIES:
            return fail(u'岗位类别不在可选范围内', 400)
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(recruitments_db.update_recruitment, key, **fields)

    @bp.route('/api/operator/recruitments/<key>', methods=['DELETE'])
    @require_capability('recruit.manage')
    def operator_recruitment_delete(key):
        return run_write(recruitments_db.delete_recruitment, key)

    # ---- 公告来源 ----

    @bp.route('/api/operator/recruitments/<key>/sources', methods=['GET'])
    @require_capability('recruit.manage')
    def operator_recruitment_sources(key):
        return ok(sources=recruitments_db.get_recruitment_sources(key))

    @bp.route('/api/operator/recruitments/<key>/sources', methods=['POST'])
    @require_capability('recruit.manage')
    def operator_recruitment_source_create(key):
        data = json_body()
        title = _text(data.get('title'), _MAX_TITLE)
        if not title:
            return fail(u'来源标题不能为空', 400)
        fields = _fields(data, ('title', 'media'))
        for column in ('date', 'url'):
            if column in data:
                fields[column] = _text(data.get(column), 200)
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        fields.pop('title', None)
        return run_write(recruitments_db.create_recruitment_source,
                         key, title, **fields)

    @bp.route('/api/operator/recruitments/sources/<int:source_id>',
              methods=['PUT'])
    @require_capability('recruit.manage')
    def operator_recruitment_source_update(source_id):
        data = json_body()
        fields = _fields(data, ('title', 'media'))
        for column in ('date', 'url'):
            if column in data:
                fields[column] = _text(data.get(column), 200)
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(recruitments_db.update_recruitment_source,
                         source_id, **fields)

    @bp.route('/api/operator/recruitments/sources/<int:source_id>',
              methods=['DELETE'])
    @require_capability('recruit.manage')
    def operator_recruitment_source_delete(source_id):
        return run_write(recruitments_db.delete_recruitment_source, source_id)


OPERATOR_RECRUITMENTS_ROUTES = (
    ('/api/operator/recruitments', 'GET'),
    ('/api/operator/recruitments', 'POST'),
    ('/api/operator/recruitments/<key>', 'PUT'),
    ('/api/operator/recruitments/<key>', 'DELETE'),
    ('/api/operator/recruitments/<key>/sources', 'GET'),
    ('/api/operator/recruitments/<key>/sources', 'POST'),
    ('/api/operator/recruitments/sources/<int:source_id>', 'PUT'),
    ('/api/operator/recruitments/sources/<int:source_id>', 'DELETE'),
)

__all__ = ['register_recruitments_routes', 'OPERATOR_RECRUITMENTS_ROUTES',
           'CAPABILITIES_USED']
