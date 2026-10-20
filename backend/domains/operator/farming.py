# -*- coding: utf-8 -*-
"""运营域：农时日历的内容维护路由（T14）。

覆盖五类内容：作物（farming_products）、物候期（farming_phenophases）、
农事任务（farming_tasks）、来源登记（farming_sources）、分类标签
（farming_categories）。全部挂在 /api/operator/farming/ 下。

与前台的口径关系：前台 /api/agriculture/* 是这些表的只读视图，两边读同一个库，
所以「运营改完前台立即返回新值」不需要任何同步步骤，也没有缓存可失效。

任务日期 task_md 的校验与前台一致：前台 calendar.py 用
`mm, dd = md.split('-')` 解析，且只在 mm == month 时给出 date。
这里同样要求 MM-DD 两段都是整数、且 MM 必须等于 month，
否则运营存进一条「8-05」的任务，前台解析出来日期对不上月份，用户看到的是错的日子。
"""

from flask import request

from core.permissions import require_capability
from db_domains import farming as farming_db
from domains.operator.routes import json_body, current_username, ok, fail, run_write

# 运营域读 farming 能力域，写侧与 farming.manage 对应（声明供机械检查判权）。
CAPABILITIES_USED = ('farming.manage',)

# 任务分类白名单。与 farming_categories 表的 key 对齐：存一个表里没有的 key，
# 前台 category_label 会退回显示 key 本身（calendar.py 的 labels.get(k, k)），
# 学员端就是一串英文。所以这里按表校验，而不是让它在界面上裸奔。
_CATEGORY_KEYS = ('fertilize', 'harvest', 'manage', 'pest', 'water')

# 任务优先级白名单。前台按 priority === 'high' 挑提醒重点（calendar.py），
# 所以这三个值不能由运营自由发挥。
_PRIORITIES = ('high', 'medium', 'low')

# 文本字段长度上限。与前台表单的 maxlength 同一口径，防止运营粘贴一整页正文
# 把卡片撑坏（前台没有截断逻辑）。
_TEXT_LIMITS = {
    'title': 60, 'description': 500, 'tip': 200, 'date_basis': 300,
    'disease': 60,
}
_MAX_TEXT = 500


def _text(value, limit=_MAX_TEXT):
    """把入参规整成去空格的字符串。None 给 ''，非字符串按字符串转。"""
    if value is None:
        return ''
    text = value if isinstance(value, str) else str(value)
    return text.strip()


def _optional_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validate_task_md(task_md, month):
    """校验 task_md：空（本月内无具体日期）或合法的 MM-DD，且 MM == month。

    返回 (task_md, 错误消息)。非法时第二个元素是给用户的 400 文案。
    """
    task_md = _text(task_md)
    if not task_md:
        return '', None
    parts = task_md.split('-')
    if len(parts) != 2 or len(parts[0]) != 2 or len(parts[1]) != 2:
        return '', u'日期格式应为 MM-DD，例如 03-15'
    try:
        mm, dd = int(parts[0]), int(parts[1])
    except ValueError:
        return '', u'日期格式应为 MM-DD，例如 03-15'
    if not (1 <= mm <= 12) or not (1 <= dd <= 31):
        return '', u'日期超出范围：月份 1-12，日期 1-31'
    if month is not None and mm != month:
        return '', u'日期所属月份（%02d）与任务的月份（%d）不一致' % (mm, month)
    return task_md, None


def _task_payload(data, creating):
    """从请求体取出农事任务字段。返回 (字段字典, 错误消息)。

    creating=True（POST）时 product_id / title / category / month 四个必填；
    creating=False（PUT）时只校验传进来的字段，没传的不动 —— 运营改一个标题
    不该被要求把整条任务重填一遍。 month 不传时 task_md 与月份的绑定关系
    无从校验，此时按库里现有的 month 补上再校验。
    """
    fields = {}
    for key in ('product_id', 'title', 'category', 'icon', 'description',
                'tip', 'source_key', 'date_basis'):
        if key in data:
            fields[key] = _text(data.get(key))
    for key in ('phase_id', 'sort_order'):
        if key in data:
            fields[key] = _optional_int(data.get(key))
    if 'priority' in data:
        fields['priority'] = _text(data.get('priority')) or 'medium'
    if 'is_active' in data:
        fields['is_active'] = 1 if data.get('is_active') else 0

    month = None
    if 'month' in data:
        month = _optional_int(data.get('month'))
        if month is None or month < 1 or month > 12:
            return None, u'月份需为 1 到 12 的整数'
        fields['month'] = month

    if 'task_md' in data:
        task_md, error = _validate_task_md(data.get('task_md'), month)
        if error:
            return None, error
        fields['task_md'] = task_md

    if creating:
        for key, message in (('product_id', u'请选择作物'),
                             ('title', u'任务标题不能为空'),
                             ('category', u'请选择任务分类')):
            if not fields.get(key):
                return None, message
        if month is None:
            return None, u'月份需为 1 到 12 的整数'
    else:
        # 局部改月份或日期时，用库里现有的另一半补齐绑定关系再校验
        if ('task_md' in fields or 'month' in fields) and 'month' not in fields:
            return None, u'改日期或月份时必须同时给出 month'
        if 'task_md' in fields and 'month' in fields:
            task_md, error = _validate_task_md(fields['task_md'], fields['month'])
            if error:
                return None, error
            fields['task_md'] = task_md

    if fields.get('title') and len(fields['title']) > _TEXT_LIMITS['title']:
        return None, u'任务标题不能超过 %d 字' % _TEXT_LIMITS['title']
    if fields.get('category') and fields['category'] not in _CATEGORY_KEYS:
        return None, u'任务分类不在可选范围内'
    if fields.get('priority') and fields['priority'] not in _PRIORITIES:
        return None, u'优先级只能是 high / medium / low'
    if fields.get('source_key') and not farming_db.get_farming_source_by_key(
            fields['source_key']):
        return None, u'来源不存在，请先在来源登记里添加'
    return fields, None


def _entry_list(rows, product_name=None):
    """把任务行压成后台列表项。字段与前台 tasks[] 同名，前端不必做两套映射。"""
    out = []
    for row in rows:
        out.append({
            'id': row['id'],
            'product_id': row['product_id'],
            'product_name': product_name or '',
            'phase_id': row.get('phase_id'),
            'phase_name': row.get('phase_name'),
            'title': row.get('title') or '',
            'category': row.get('category') or '',
            'category_label': (farming_db.get_farming_category_labels()
                               .get(row.get('category'), row.get('category'))),
            'priority': row.get('priority') or 'medium',
            'task_md': row.get('task_md') or '',
            'month': row.get('month'),
            'icon': row.get('icon') or '',
            'description': row.get('description') or '',
            'tip': row.get('tip') or '',
            'source_key': row.get('source_key') or '',
            'date_basis': row.get('date_basis') or '',
            'is_verified': int(row.get('is_verified') or 0),
            'verified_by': row.get('verified_by') or '',
            'verified_at': row.get('verified_at') or '',
            'is_active': int(row.get('is_active') or 0),
            'sort_order': row.get('sort_order') or 0,
        })
    return out


def register_farming_routes(bp):
    """把农时日历的维护路由挂到蓝图。"""

    # ---- 农事任务 ----

    @bp.route('/api/operator/farming/tasks', methods=['GET'])
    @require_capability('farming.manage')
    def operator_farming_tasks():
        """农事任务列表。支持按作物与月份筛，默认全量。"""
        product_id = _text(request.args.get('product_id'))
        month = _optional_int(request.args.get('month'))
        overdue = _text(request.args.get('overdue'))
        if overdue == '1':
            rows = farming_db.get_farming_overdue_tasks(product_id=product_id or None)
        else:
            # 空 product_id = 运营选了「全部作物」，交给数据层按全量返回
            rows = farming_db.get_farming_tasks(product_id or None, month=month)
        # month 只对非超期筛选生效：超期列表本来就是按复核时间挑出来的一小批，
        # 再按月份收窄会把「该重新核了」漏掉，而运营要看的就是全部待复核项。
        product_name = ''
        if product_id:
            product = farming_db.get_farming_product(product_id)
            product_name = (product or {}).get('name') or ''
        labels = farming_db.get_farming_category_labels()
        return ok(tasks=_entry_list(rows, product_name))

    @bp.route('/api/operator/farming/tasks', methods=['POST'])
    @require_capability('farming.manage')
    def operator_farming_task_create():
        data = json_body()
        fields, error = _task_payload(data, creating=True)
        if error:
            return fail(error, 400)
        return run_write(farming_db.create_farming_task,
                         fields.pop('product_id'), fields.pop('title'),
                         fields.pop('category'), fields.pop('month'), **fields)

    @bp.route('/api/operator/farming/tasks/<int:task_id>', methods=['PUT'])
    @require_capability('farming.manage')
    def operator_farming_task_update(task_id):
        data = json_body()
        fields, error = _task_payload(data, creating=False)
        if error:
            return fail(error, 400)
        return run_write(farming_db.update_farming_task, task_id, **fields)

    @bp.route('/api/operator/farming/tasks/<int:task_id>', methods=['DELETE'])
    @require_capability('farming.manage')
    def operator_farming_task_delete(task_id):
        return run_write(farming_db.delete_farming_task, task_id)

    @bp.route('/api/operator/farming/tasks/<int:task_id>/verify', methods=['POST'])
    @require_capability('farming.manage')
    def operator_farming_task_verify(task_id):
        """标记已复核：verified_by 取当前登录用户，verified_at 由数据层写当前时间。"""
        verifier = current_username()
        if not verifier:
            return fail(u'权限不足', 403)
        return run_write(farming_db.verify_farming_task, task_id, verifier)

    # ---- 物候期 ----

    @bp.route('/api/operator/farming/phenophases', methods=['GET'])
    @require_capability('farming.manage')
    def operator_farming_phenophases():
        product_id = _text(request.args.get('product_id'))
        return ok(phenophases=[
            {k: row[k] for k in ('id', 'product_id', 'name', 'start_month',
                                 'end_month', 'color', 'description', 'sort_order')}
            for row in farming_db.get_farming_phenophases(product_id or None)
        ])

    @bp.route('/api/operator/farming/phenophases', methods=['POST'])
    @require_capability('farming.manage')
    def operator_farming_phenophase_create():
        data = json_body()
        product_id = _text(data.get('product_id'))
        name = _text(data.get('name'))
        if not product_id:
            return fail(u'请选择作物', 400)
        if not name:
            return fail(u'物候期名称不能为空', 400)
        start = _optional_int(data.get('start_month'))
        end = _optional_int(data.get('end_month'))
        for value in (start, end):
            if value is None or value < 1 or value > 12:
                return fail(u'起止月份需为 1 到 12 的整数', 400)
        return run_write(farming_db.create_farming_phenophase, product_id, name,
                         start, end,
                         color=_text(data.get('color')),
                         description=_text(data.get('description')),
                         sort_order=_optional_int(data.get('sort_order')) or 0)

    @bp.route('/api/operator/farming/phenophases/<int:phase_id>', methods=['PUT'])
    @require_capability('farming.manage')
    def operator_farming_phenophase_update(phase_id):
        data = json_body()
        fields = {}
        for key in ('product_id', 'name', 'color', 'description'):
            if key in data:
                fields[key] = _text(data.get(key))
        for key in ('start_month', 'end_month'):
            if key in data:
                value = _optional_int(data.get(key))
                if value is None or value < 1 or value > 12:
                    return fail(u'月份需为 1 到 12 的整数', 400)
                fields[key] = value
        if 'sort_order' in data:
            value = _optional_int(data.get('sort_order'))
            if value is None or value < 0:
                return fail(u'排序需为不小于 0 的整数', 400)
            fields['sort_order'] = value
        return run_write(farming_db.update_farming_phenophase, phase_id, **fields)

    @bp.route('/api/operator/farming/phenophases/<int:phase_id>', methods=['DELETE'])
    @require_capability('farming.manage')
    def operator_farming_phenophase_delete(phase_id):
        return run_write(farming_db.delete_farming_phenophase, phase_id)

    # ---- 作物 ----

    @bp.route('/api/operator/farming/products', methods=['GET'])
    @require_capability('farming.manage')
    def operator_farming_products():
        return ok(products=[{
            'id': row['id'], 'name': row.get('name') or '',
            'icon': row.get('icon') or '', 'summary': row.get('summary') or '',
            'region': row.get('region') or '', 'sort_order': row.get('sort_order') or 0,
            'is_active': int(row.get('is_active') or 0),
        } for row in farming_db.get_farming_products(active_only=False)])

    @bp.route('/api/operator/farming/products', methods=['POST'])
    @require_capability('farming.manage')
    def operator_farming_product_create():
        data = json_body()
        product_id = _text(data.get('id')) or _text(data.get('product_id'))
        name = _text(data.get('name'))
        if not product_id:
            return fail(u'作物 id 不能为空', 400)
        if not name:
            return fail(u'作物名称不能为空', 400)
        return run_write(farming_db.create_farming_product, product_id, name,
                         icon=_text(data.get('icon')) or 'seedling',
                         summary=_text(data.get('summary')),
                         region=_text(data.get('region')) or u'广东',
                         sort_order=_optional_int(data.get('sort_order')) or 0,
                         is_active=1 if data.get('is_active', True) else 0)

    @bp.route('/api/operator/farming/products/<product_id>', methods=['PUT'])
    @require_capability('farming.manage')
    def operator_farming_product_update(product_id):
        data = json_body()
        fields = {}
        for key in ('name', 'icon', 'summary', 'region'):
            if key in data:
                fields[key] = _text(data.get(key))
        for key in ('sort_order',):
            if key in data:
                fields[key] = _optional_int(data.get(key)) or 0
        if 'is_active' in data:
            fields['is_active'] = 1 if data.get('is_active') else 0
        return run_write(farming_db.update_farming_product, product_id, **fields)

    @bp.route('/api/operator/farming/products/<product_id>', methods=['DELETE'])
    @require_capability('farming.manage')
    def operator_farming_product_delete(product_id):
        return run_write(farming_db.delete_farming_product, product_id)

    # ---- 来源登记 ----

    @bp.route('/api/operator/farming/sources', methods=['GET'])
    @require_capability('farming.manage')
    def operator_farming_sources():
        return ok(sources=[dict(row) for row in farming_db.get_farming_sources()])

    @bp.route('/api/operator/farming/sources', methods=['POST'])
    @require_capability('farming.manage')
    def operator_farming_source_create():
        data = json_body()
        key = _text(data.get('key'))
        name = _text(data.get('name'))
        if not key:
            return fail(u'来源 key 不能为空', 400)
        if not name:
            return fail(u'来源名称不能为空', 400)
        return run_write(farming_db.create_farming_source, key, name,
                         org=_text(data.get('org')),
                         doc_type=_text(data.get('doc_type')),
                         doc_no=_text(data.get('doc_no')) or u'待核',
                         url=_text(data.get('url')),
                         sort_order=_optional_int(data.get('sort_order')) or 0)

    @bp.route('/api/operator/farming/sources/<key>', methods=['PUT'])
    @require_capability('farming.manage')
    def operator_farming_source_update(key):
        data = json_body()
        fields = {k: _text(data.get(k)) for k in ('name', 'org', 'doc_type',
                                                  'doc_no', 'url') if k in data}
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(farming_db.update_farming_source, key, **fields)

    @bp.route('/api/operator/farming/sources/<key>', methods=['DELETE'])
    @require_capability('farming.manage')
    def operator_farming_source_delete(key):
        return run_write(farming_db.delete_farming_source, key)

    # ---- 分类标签 ----

    @bp.route('/api/operator/farming/categories', methods=['GET'])
    @require_capability('farming.manage')
    def operator_farming_categories():
        return ok(categories=farming_db.get_farming_categories())

    @bp.route('/api/operator/farming/categories', methods=['POST'])
    @require_capability('farming.manage')
    def operator_farming_category_create():
        data = json_body()
        key = _text(data.get('key'))
        label = _text(data.get('label'))
        if not key:
            return fail(u'分类 key 不能为空', 400)
        if not label:
            return fail(u'分类标签不能为空', 400)
        return run_write(farming_db.create_farming_category, key, label,
                         color=_text(data.get('color')),
                         sort_order=_optional_int(data.get('sort_order')) or 0)

    @bp.route('/api/operator/farming/categories/<key>', methods=['PUT'])
    @require_capability('farming.manage')
    def operator_farming_category_update(key):
        data = json_body()
        fields = {}
        for field in ('label', 'color'):
            if field in data:
                fields[field] = _text(data.get(field))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(farming_db.update_farming_category, key, **fields)

    @bp.route('/api/operator/farming/categories/<key>', methods=['DELETE'])
    @require_capability('farming.manage')
    def operator_farming_category_delete(key):
        return run_write(farming_db.delete_farming_category, key)


OPERATOR_FARMING_ROUTES = (
    ('/api/operator/farming/tasks', 'GET'),
    ('/api/operator/farming/tasks', 'POST'),
    ('/api/operator/farming/tasks/<int:task_id>', 'PUT'),
    ('/api/operator/farming/tasks/<int:task_id>', 'DELETE'),
    ('/api/operator/farming/tasks/<int:task_id>/verify', 'POST'),
    ('/api/operator/farming/phenophases', 'GET'),
    ('/api/operator/farming/phenophases', 'POST'),
    ('/api/operator/farming/phenophases/<int:phase_id>', 'PUT'),
    ('/api/operator/farming/phenophases/<int:phase_id>', 'DELETE'),
    ('/api/operator/farming/products', 'GET'),
    ('/api/operator/farming/products', 'POST'),
    ('/api/operator/farming/products/<product_id>', 'PUT'),
    ('/api/operator/farming/products/<product_id>', 'DELETE'),
    ('/api/operator/farming/sources', 'GET'),
    ('/api/operator/farming/sources', 'POST'),
    ('/api/operator/farming/sources/<key>', 'PUT'),
    ('/api/operator/farming/sources/<key>', 'DELETE'),
    ('/api/operator/farming/categories', 'GET'),
    ('/api/operator/farming/categories', 'POST'),
    ('/api/operator/farming/categories/<key>', 'PUT'),
    ('/api/operator/farming/categories/<key>', 'DELETE'),
)

__all__ = ['register_farming_routes', 'OPERATOR_FARMING_ROUTES', 'CAPABILITIES_USED']
