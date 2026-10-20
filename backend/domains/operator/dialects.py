# -*- coding: utf-8 -*-
"""运营域：方言知识的内容维护路由（T15）。

覆盖三层内容：方言（dialects）、短语（dialect_phrases）、快捷问题
（dialect_quick_questions）。全部挂在 /api/operator/dialects/ 下。

与前台的口径关系：前台 /api/resources/dialects 与 /api/resources/dialect-info
是这些表的只读视图，两边读同一个库，所以「运营改完前台立即返回新值」
不需要任何同步步骤。

数据形状：库里方言层 + 短语 + 快问是三张表，前台要的是单个 dict

    {'id', 'name', ..., 'features': [...], 'phrases': [...], 'quick_questions': [...]}

写侧按平表收口，读侧的 get_dialect_info() 负责组装。features 列在库里是
JSON 文本，写侧只接受数组（与读侧 _decode_features 对称：读侧解析失败给
空列表，写侧就必须拒绝写坏，否则「运营以为自己写了特色标签」看不出痕迹）。

快捷问题在前台是**纯字符串数组**（detail['quick_questions'] = [str, ...]），
所以后台只编辑 question 一列，不发明别的字段。
"""

from core.permissions import require_capability
from db_domains import dialects as dialects_db
from domains.operator.routes import json_body, ok, fail, run_write

# 运营域读 dialect 能力域，写侧与 dialect.manage 对应（声明供机械检查判权）。
CAPABILITIES_USED = ('dialect.manage',)

_MAX_TEXT = 500
_MAX_TITLE = 60


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


def _features(data):
    """取 features 入参。返回 (值, 错误消息)。缺省表示「不碰这一列」。"""
    if 'features' not in data:
        return None, None
    raw = data.get('features')
    if raw is None:
        return [], None
    if isinstance(raw, tuple):
        raw = list(raw)
    if not isinstance(raw, list):
        return None, u'features 需要是数组'
    return [_text(item, _MAX_TITLE) for item in raw], None


def register_dialects_routes(bp):
    """把方言知识的维护路由挂到蓝图。"""

    # ---- 方言 ----

    @bp.route('/api/operator/dialects', methods=['GET'])
    @require_capability('dialect.manage')
    def operator_dialects():
        """方言列表，带短语与快问条数，供后台判断「这种方言填全了没有」。"""
        dialects = []
        for summary in dialects_db.get_dialects():
            dialect = dialects_db.get_dialect_editor_row(
                summary['id']) or dict(summary)
            dialect['phrase_count'] = len(
                dialects_db.get_dialect_phrases(dialect['id']))
            dialect['question_count'] = len(
                dialects_db.get_dialect_quick_questions(dialect['id']))
            dialect['feature_count'] = len(dialect.get('features') or [])
            dialects.append(dialect)
        return ok(dialects=dialects)

    @bp.route('/api/operator/dialects', methods=['POST'])
    @require_capability('dialect.manage')
    def operator_dialect_create():
        data = json_body()
        dialect_id = _text(data.get('id'))
        name = _text(data.get('name'), _MAX_TITLE)
        if not dialect_id:
            return fail(u'方言 id 不能为空', 400)
        if not name:
            return fail(u'方言名称不能为空', 400)
        fields = _fields(data, ('name', 'region', 'emoji', 'areas', 'speakers',
                                'greeting', 'greeting_meaning'))
        features, error = _features(data)
        if error:
            return fail(error, 400)
        if features is not None:
            fields['features'] = features
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        fields.pop('name', None)
        return run_write(dialects_db.create_dialect, dialect_id, name, **fields)

    @bp.route('/api/operator/dialects/<dialect_id>', methods=['PUT'])
    @require_capability('dialect.manage')
    def operator_dialect_update(dialect_id):
        data = json_body()
        fields = _fields(data, ('name', 'region', 'emoji', 'areas', 'speakers',
                                'greeting', 'greeting_meaning'))
        features, error = _features(data)
        if error:
            return fail(error, 400)
        if features is not None:
            fields['features'] = features
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(dialects_db.update_dialect, dialect_id, **fields)

    @bp.route('/api/operator/dialects/<dialect_id>', methods=['DELETE'])
    @require_capability('dialect.manage')
    def operator_dialect_delete(dialect_id):
        if dialect_id == FALLBACK_DIALECT_ID:
            return fail(u'%s 是前台未知方言的兜底，不能删除' % dialect_id, 400)
        return run_write(dialects_db.delete_dialect, dialect_id)

    # ---- 短语 ----

    @bp.route('/api/operator/dialects/<dialect_id>/phrases', methods=['GET'])
    @require_capability('dialect.manage')
    def operator_dialect_phrases(dialect_id):
        return ok(phrases=dialects_db.get_dialect_phrases(dialect_id))

    @bp.route('/api/operator/dialects/<dialect_id>/phrases', methods=['POST'])
    @require_capability('dialect.manage')
    def operator_dialect_phrase_create(dialect_id):
        data = json_body()
        fields = _fields(data, ('dialect', 'mandarin', 'pinyin'))
        if not fields.get('mandarin'):
            return fail(u'普通话说法不能为空', 400)
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(dialects_db.create_dialect_phrase, dialect_id, **fields)

    @bp.route('/api/operator/dialects/phrases/<int:phrase_id>', methods=['PUT'])
    @require_capability('dialect.manage')
    def operator_dialect_phrase_update(phrase_id):
        data = json_body()
        fields = _fields(data, ('dialect', 'mandarin', 'pinyin'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(dialects_db.update_dialect_phrase, phrase_id, **fields)

    @bp.route('/api/operator/dialects/phrases/<int:phrase_id>', methods=['DELETE'])
    @require_capability('dialect.manage')
    def operator_dialect_phrase_delete(phrase_id):
        return run_write(dialects_db.delete_dialect_phrase, phrase_id)

    # ---- 快捷问题 ----

    @bp.route('/api/operator/dialects/<dialect_id>/quick-questions',
              methods=['GET'])
    @require_capability('dialect.manage')
    def operator_dialect_quick_questions(dialect_id):
        return ok(questions=dialects_db.get_dialect_quick_questions(dialect_id))

    @bp.route('/api/operator/dialects/<dialect_id>/quick-questions',
              methods=['POST'])
    @require_capability('dialect.manage')
    def operator_dialect_quick_question_create(dialect_id):
        data = json_body()
        question = _text(data.get('question'))
        if not question:
            return fail(u'快捷问题不能为空', 400)
        fields = {}
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(dialects_db.create_dialect_quick_question,
                         dialect_id, question, **fields)

    @bp.route('/api/operator/dialects/quick-questions/<int:question_id>',
              methods=['PUT'])
    @require_capability('dialect.manage')
    def operator_dialect_quick_question_update(question_id):
        data = json_body()
        fields = {}
        if 'question' in data:
            fields['question'] = _text(data.get('question'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(dialects_db.update_dialect_quick_question,
                         question_id, **fields)

    @bp.route('/api/operator/dialects/quick-questions/<int:question_id>',
              methods=['DELETE'])
    @require_capability('dialect.manage')
    def operator_dialect_quick_question_delete(question_id):
        return run_write(dialects_db.delete_dialect_quick_question, question_id)


OPERATOR_DIALECTS_ROUTES = (
    ('/api/operator/dialects', 'GET'),
    ('/api/operator/dialects', 'POST'),
    ('/api/operator/dialects/<dialect_id>', 'PUT'),
    ('/api/operator/dialects/<dialect_id>', 'DELETE'),
    ('/api/operator/dialects/<dialect_id>/phrases', 'GET'),
    ('/api/operator/dialects/<dialect_id>/phrases', 'POST'),
    ('/api/operator/dialects/phrases/<int:phrase_id>', 'PUT'),
    ('/api/operator/dialects/phrases/<int:phrase_id>', 'DELETE'),
    ('/api/operator/dialects/<dialect_id>/quick-questions', 'GET'),
    ('/api/operator/dialects/<dialect_id>/quick-questions', 'POST'),
    ('/api/operator/dialects/quick-questions/<int:question_id>', 'PUT'),
    ('/api/operator/dialects/quick-questions/<int:question_id>', 'DELETE'),
)

__all__ = ['register_dialects_routes', 'OPERATOR_DIALECTS_ROUTES',
           'CAPABILITIES_USED']
CAPABILITIES_USED = ('dialect.manage',)

_MAX_TEXT = 500
_MAX_TITLE = 60

# 前台兜底方言的 id。resources/routes.py 的 get_dialect_info 在查不到入参方言时
# 退回这一个（`if d is None: d = dialects_db.get_dialect_info('cantonese')`），
# 删掉它会让「未知方言 id」这个分支直接 500。所以这个 id 不允许删：
# 不是权限问题，是前台有一处写死的依赖。
FALLBACK_DIALECT_ID = 'cantonese'
