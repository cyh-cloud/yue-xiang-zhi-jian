# -*- coding: utf-8 -*-
"""运营域：病虫害知识的内容维护路由（T14）。

覆盖三类内容：条目（pest_entries）、来源（pest_sources）、
实拍图关联（pest_images，一条条目最多一张）。作物层（pest_crops）的增删改
也在这里，因为条目必须挂在一个已存在的作物下。

与前台的口径关系：前台 /api/agriculture/pest-knowledge 是这些表的只读视图，
两边读同一个库，所以「运营改完前台立即返回新值」不需要任何同步步骤。

两条硬约定在写侧同样成立（读侧在 db_domains.pest，两边一起守住）：

1. 来源必须是 pest_sources 里已登记的 key。写一个不存在的 key，
   前台 sources 会静默丢掉它（knowledge.py 的 `if key in source_map`），
   学员端看到「未登记具体出处」，而运营以为自己写了出处；
2. 实拍图只有拿到授权的才能写 file。不写 file 等于没有图，前台显示
   「暂无实拍图」，绝不用一张示意图占位。

五个 JSON 列（symptoms / treatment / prevention / registered / chem_table）
的入参只接受数组，空数组写 '[]'。这与前台 pest_entry_view 的形状一致：
非数组会被读侧 _json_list 判成 []，写侧拒绝是为了让「传错了」当场可见。
"""

from flask import request

from core.permissions import require_capability
from db_domains import pest as pest_db
from domains.operator.routes import json_body, current_username, ok, fail, run_write

# 运营域读 pest 能力域，写侧与 pest.manage 对应（声明供机械检查判权）。
CAPABILITIES_USED = ('pest.manage',)

# 条目类型白名单。前台 pest-knowledge 的 kind 筛选只认这两个值
# （knowledge.py 的 `kind not in ('disease', 'pest')` 会 400）。
_KINDS = ('disease', 'pest')

# 五个 JSON 列。入参必须是数组，写侧按原样序列化回库。
_JSON_COLUMNS = ('symptoms', 'treatment', 'prevention', 'registered', 'chem_table')

# 文本字段长度上限，与前台表单的 maxlength 同一口径。
_MAX_DISEASE = 60
_MAX_TEXT = 500


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


def _json_field(data, key):
    """取一个 JSON 列。返回 (值, 错误消息)。空值与缺省都给 []。"""
    raw = data.get(key)
    if raw is None:
        return [], None
    if isinstance(raw, tuple):
        raw = list(raw)
    if not isinstance(raw, list):
        return None, u'%s 需要是数组' % key
    return [_text(item, _MAX_TEXT) for item in raw], None


def _entry_payload(data):
    """从请求体取出病虫害条目字段。返回 (字段字典, 错误消息)。"""
    fields = {}
    for key in ('crop_id', 'disease', 'alias', 'kind', 'pathogen', 'part',
                'severity', 'occurrence', 'safety_note'):
        if key in data:
            fields[key] = _text(data.get(key))
    for key in ('sort_order',):
        if key in data:
            fields[key] = _optional_int(data.get(key)) or 0
    if 'is_verified' in data:
        fields['is_verified'] = 1 if data.get('is_verified') else 0

    if fields.get('crop_id') == '':
        return None, u'请选择作物'
    if fields.get('disease') == '':
        return None, u'病害名称不能为空'
    if len(fields.get('disease', '')) > _MAX_DISEASE:
        return None, u'病害名称不能超过 %d 字' % _MAX_DISEASE
    if 'kind' in fields and fields['kind'] and fields['kind'] not in _KINDS:
        return None, u'类型只能是 disease 或 pest'

    for column in _JSON_COLUMNS:
        if column in data:
            value, error = _json_field(data, column)
            if error:
                return None, error
            fields[column] = value

    if 'crop_id' in fields and not pest_db.get_pest_crop(fields['crop_id']):
        return None, u'作物不存在，请先在作物列表里添加'
    return fields, None


def _image_payload(data):
    fields = {}
    for key in ('file', 'credit', 'license', 'caption', 'source_url',
                'shot_date', 'note'):
        if key in data:
            fields[key] = _text(data.get(key))
    return fields


def register_pest_routes(bp):
    """把病虫害知识的维护路由挂到蓝图。"""

    # ---- 条目 ----

    @bp.route('/api/operator/pest/entries', methods=['GET'])
    @require_capability('pest.manage')
    def operator_pest_entries():
        crop_id = _text(request.args.get('crop_id'))
        overdue = _text(request.args.get('overdue'))
        if overdue == '1':
            entries = pest_db.get_overdue_pest_entries(crop_id=crop_id or None)
            items = [{
                'id': row['id'], 'crop_id': row['crop_id'],
                'crop_name': row.get('crop_name') or '',
                'disease': row.get('disease') or '',
                'kind': row.get('kind') or '',
                'is_verified': int(row.get('is_verified') or 0),
                'verified_by': row.get('verified_by') or '',
                'verified_at': row.get('verified_at') or '',
            } for row in entries]
        else:
            items = [{
                'id': row['id'], 'crop_id': row['crop'],
                'crop_name': row.get('crop_name') or '',
                'disease': row.get('disease') or '',
                'kind': row.get('kind') or '',
                'is_verified': int(row.get('is_verified') or 0),
                'verified_by': row.get('verified_by') or '',
                'verified_at': row.get('verified_at') or '',
            } for row in pest_db.get_pest_entries(
                    crop_id=crop_id or None, with_details=False)]
        return ok(entries=items)

    @bp.route('/api/operator/pest/entries', methods=['POST'])
    @require_capability('pest.manage')
    def operator_pest_entry_create():
        data = json_body()
        entry_id = _text(data.get('id'))
        if not entry_id:
            return fail(u'条目 id 不能为空', 400)
        fields, error = _entry_payload(data)
        if error:
            return fail(error, 400)
        source_keys = data.get('source_keys')
        if source_keys is not None and not isinstance(source_keys, list):
            return fail(u'source_keys 需要是数组', 400)
        return run_write(pest_db.create_pest_entry, entry_id,
                         fields.pop('crop_id'), fields.pop('disease'),
                         source_keys=source_keys, **fields)

    @bp.route('/api/operator/pest/entries/<entry_id>', methods=['PUT'])
    @require_capability('pest.manage')
    def operator_pest_entry_update(entry_id):
        data = json_body()
        fields, error = _entry_payload(data)
        if error:
            return fail(error, 400)
        source_keys = data.get('source_keys')
        if source_keys is not None and not isinstance(source_keys, list):
            return fail(u'source_keys 需要是数组', 400)
        return run_write(pest_db.update_pest_entry, entry_id,
                         source_keys=source_keys, **fields)

    @bp.route('/api/operator/pest/entries/<entry_id>', methods=['DELETE'])
    @require_capability('pest.manage')
    def operator_pest_entry_delete(entry_id):
        return run_write(pest_db.delete_pest_entry, entry_id)

    @bp.route('/api/operator/pest/entries/<entry_id>/verify', methods=['POST'])
    @require_capability('pest.manage')
    def operator_pest_entry_verify(entry_id):
        """标记已复核：verified_by 取当前登录用户，verified_at 由数据层写当前时间。"""
        verifier = current_username()
        if not verifier:
            return fail(u'权限不足', 403)
        return run_write(pest_db.verify_pest_entry, entry_id, verifier)

    # ---- 实拍图关联 ----

    @bp.route('/api/operator/pest/entries/<entry_id>/image', methods=['PUT'])
    @require_capability('pest.manage')
    def operator_pest_image_set(entry_id):
        data = json_body()
        fields = _image_payload(data)
        return run_write(pest_db.set_pest_image, entry_id, **fields)

    @bp.route('/api/operator/pest/entries/<entry_id>/image', methods=['DELETE'])
    @require_capability('pest.manage')
    def operator_pest_image_delete(entry_id):
        return run_write(pest_db.delete_pest_image, entry_id)

    # ---- 来源 ----

    @bp.route('/api/operator/pest/sources', methods=['GET'])
    @require_capability('pest.manage')
    def operator_pest_sources():
        return ok(sources=list(pest_db.get_pest_source_map().values()))

    @bp.route('/api/operator/pest/sources', methods=['POST'])
    @require_capability('pest.manage')
    def operator_pest_source_create():
        data = json_body()
        key = _text(data.get('key'))
        name = _text(data.get('name'))
        if not key:
            return fail(u'来源 key 不能为空', 400)
        if not name:
            return fail(u'来源名称不能为空', 400)
        return run_write(pest_db.create_pest_source, key, name,
                         org=_text(data.get('org')),
                         doc_type=_text(data.get('doc_type')),
                         doc_no=_text(data.get('doc_no')),
                         date=_text(data.get('date')),
                         url=_text(data.get('url')),
                         sort_order=_optional_int(data.get('sort_order')) or 0)

    @bp.route('/api/operator/pest/sources/<key>', methods=['PUT'])
    @require_capability('pest.manage')
    def operator_pest_source_update(key):
        data = json_body()
        fields = {k: _text(data.get(k)) for k in
                  ('name', 'org', 'doc_type', 'doc_no', 'date', 'url') if k in data}
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(pest_db.update_pest_source, key, **fields)

    @bp.route('/api/operator/pest/sources/<key>', methods=['DELETE'])
    @require_capability('pest.manage')
    def operator_pest_source_delete(key):
        return run_write(pest_db.delete_pest_source, key)

    # ---- 作物 ----

    @bp.route('/api/operator/pest/crops', methods=['GET'])
    @require_capability('pest.manage')
    def operator_pest_crops():
        return ok(crops=pest_db.get_pest_crops())

    @bp.route('/api/operator/pest/crops', methods=['POST'])
    @require_capability('pest.manage')
    def operator_pest_crop_create():
        data = json_body()
        crop_id = _text(data.get('id'))
        name = _text(data.get('name'))
        if not crop_id:
            return fail(u'作物 id 不能为空', 400)
        if not name:
            return fail(u'作物名称不能为空', 400)
        return run_write(pest_db.create_pest_crop, crop_id, name,
                         icon=_text(data.get('icon')),
                         summary=_text(data.get('summary')),
                         sort_order=_optional_int(data.get('sort_order')) or 0)

    @bp.route('/api/operator/pest/crops/<crop_id>', methods=['PUT'])
    @require_capability('pest.manage')
    def operator_pest_crop_update(crop_id):
        data = json_body()
        fields = {k: _text(data.get(k)) for k in ('name', 'icon', 'summary')
                  if k in data}
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(pest_db.update_pest_crop, crop_id, **fields)

    @bp.route('/api/operator/pest/crops/<crop_id>', methods=['DELETE'])
    @require_capability('pest.manage')
    def operator_pest_crop_delete(crop_id):
        return run_write(pest_db.delete_pest_crop, crop_id)


OPERATOR_PEST_ROUTES = (
    ('/api/operator/pest/entries', 'GET'),
    ('/api/operator/pest/entries', 'POST'),
    ('/api/operator/pest/entries/<entry_id>', 'PUT'),
    ('/api/operator/pest/entries/<entry_id>', 'DELETE'),
    ('/api/operator/pest/entries/<entry_id>/verify', 'POST'),
    ('/api/operator/pest/entries/<entry_id>/image', 'PUT'),
    ('/api/operator/pest/entries/<entry_id>/image', 'DELETE'),
    ('/api/operator/pest/sources', 'GET'),
    ('/api/operator/pest/sources', 'POST'),
    ('/api/operator/pest/sources/<key>', 'PUT'),
    ('/api/operator/pest/sources/<key>', 'DELETE'),
    ('/api/operator/pest/crops', 'GET'),
    ('/api/operator/pest/crops', 'POST'),
    ('/api/operator/pest/crops/<crop_id>', 'PUT'),
    ('/api/operator/pest/crops/<crop_id>', 'DELETE'),
)

__all__ = ['register_pest_routes', 'OPERATOR_PEST_ROUTES', 'CAPABILITIES_USED']