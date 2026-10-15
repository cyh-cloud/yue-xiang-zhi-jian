# -*- coding: utf-8 -*-
"""运营域：成功案例的内容维护路由（T15）。

覆盖五层内容：案例（success_cases）与四个子表 —— 数据指标（case_stats）、
里程碑（case_milestones）、来源（case_sources）、借鉴点（case_lessons）。
全部挂在 /api/operator/cases/ 下。

与前台的口径关系：前台 /api/resources/cases 是这些表的只读视图，但中间多
一道审核门禁（只下发 content_reviews 里 status='approved' 的案例，见
db_domains.resources.get_success_cases）。所以「运营改完前台立即生效」对案例
有一条额外前提：这条案例已经过审。新建案例一律先进审核队列，
由超级管理员在 admin.html 裁定，运营侧看不到也改不了别人的裁定结果。

数据形状：库里五张表是拆平的，前台要的是单个 dict

    {'id', 'title', ..., 'stats': [...], 'milestones': [...],
     'sources': [...], 'lessons': [str, ...]}

写侧按平表收口，读侧的 content.get_case() 负责按 sort_order 组装。
注意 lessons 在前台是纯字符串数组，所以后台只编辑 text 一列。

删案例会连带清掉它的审核记录（数据层已收敛到 reviews 域的
delete_reviews_for），否则学员端会留下一张看不到内容的审核卡片。
"""

import json

from core.permissions import require_capability
from db_domains import content as content_db
from db_domains import resources as resources_db
from domains.operator.routes import json_body, current_username, ok, fail, run_write

# 运营域读 case 能力域，写侧与 case.manage 对应（声明供机械检查判权）。
# 注意 case.manage 还含 government：政府人员也能维护案例内容（T01 能力表）。
CAPABILITIES_USED = ('case.manage',)

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


def register_cases_routes(bp):
    """把成功案例的维护路由挂到蓝图。"""

    # ---- 案例 ----

    @bp.route('/api/operator/cases', methods=['GET'])
    @require_capability('case.manage')
    def operator_cases():
        """案例列表，带四个子表的条数，供后台判断「这条案例填全了没有」。"""
        cases = []
        for row in content_db.get_cases():
            case = dict(row)
            case['stat_count'] = len(case['stats'])
            case['milestone_count'] = len(case['milestones'])
            case['source_count'] = len(case['sources'])
            case['lesson_count'] = len(case['lessons'])
            for key in ('stats', 'milestones', 'sources', 'lessons'):
                case.pop(key)
            cases.append(case)
        return ok(cases=cases)

    @bp.route('/api/operator/cases', methods=['POST'])
    @require_capability('case.manage')
    def operator_case_create():
        data = json_body()
        title = _text(data.get('title'), _MAX_TITLE)
        if not title:
            return fail(u'案例标题不能为空', 400)
        fields = _fields(data, ('title', 'region', 'location', 'background',
                                'description', 'quote', 'quote_author'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        fields.pop('title', None)
        # run_write 返回 (Response, status) 二元组，不是 Response：它给路由层
        # 留了「同一动作也要能回非 200」的余地。这里需要拿到新建的 id，
        # 所以把响应体读出来；失败时原样回传，不吞错误。
        response, status = run_write(content_db.create_case, title, **fields)
        if status != 200:
            return response, status
        created = json.loads(response.data)['result']
        # 新案例先进审核队列：不过审学员端看不到，所以这一步不能省
        # （省了就是「运营发了、学员永远看不到、还不报错」）。
        resources_db.create_case_review(created, current_username())
        return response, status

    @bp.route('/api/operator/cases/<int:case_id>', methods=['PUT'])
    @require_capability('case.manage')
    def operator_case_update(case_id):
        data = json_body()
        fields = _fields(data, ('title', 'region', 'location', 'background',
                                'description', 'quote', 'quote_author'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(content_db.update_case, case_id, **fields)

    @bp.route('/api/operator/cases/<int:case_id>', methods=['DELETE'])
    @require_capability('case.manage')
    def operator_case_delete(case_id):
        return run_write(content_db.delete_case, case_id)

    # ---- 数据指标 ----

    @bp.route('/api/operator/cases/<int:case_id>/stats', methods=['GET'])
    @require_capability('case.manage')
    def operator_case_stats(case_id):
        return ok(stats=content_db.get_case_stats(case_id))

    @bp.route('/api/operator/cases/<int:case_id>/stats', methods=['POST'])
    @require_capability('case.manage')
    def operator_case_stat_create(case_id):
        data = json_body()
        label = _text(data.get('label'), _MAX_TITLE)
        if not label:
            return fail(u'指标名称不能为空', 400)
        fields = _fields(data, ('label', 'value', 'icon'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        fields.pop('label', None)
        return run_write(content_db.create_case_stat, case_id, label, **fields)

    @bp.route('/api/operator/cases/stats/<int:stat_id>', methods=['PUT'])
    @require_capability('case.manage')
    def operator_case_stat_update(stat_id):
        data = json_body()
        fields = _fields(data, ('label', 'value', 'icon'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(content_db.update_case_stat, stat_id, **fields)

    @bp.route('/api/operator/cases/stats/<int:stat_id>', methods=['DELETE'])
    @require_capability('case.manage')
    def operator_case_stat_delete(stat_id):
        return run_write(content_db.delete_case_stat, stat_id)

    # ---- 里程碑 ----

    @bp.route('/api/operator/cases/<int:case_id>/milestones', methods=['GET'])
    @require_capability('case.manage')
    def operator_case_milestones(case_id):
        return ok(milestones=content_db.get_case_milestones(case_id))

    @bp.route('/api/operator/cases/<int:case_id>/milestones', methods=['POST'])
    @require_capability('case.manage')
    def operator_case_milestone_create(case_id):
        data = json_body()
        title = _text(data.get('title'), _MAX_TITLE)
        if not title:
            return fail(u'里程碑标题不能为空', 400)
        fields = _fields(data, ('period', 'title', 'desc'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        fields.pop('title', None)
        return run_write(content_db.create_case_milestone, case_id, title, **fields)

    @bp.route('/api/operator/cases/milestones/<int:milestone_id>',
              methods=['PUT'])
    @require_capability('case.manage')
    def operator_case_milestone_update(milestone_id):
        data = json_body()
        fields = _fields(data, ('period', 'title', 'desc'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(content_db.update_case_milestone, milestone_id, **fields)

    @bp.route('/api/operator/cases/milestones/<int:milestone_id>',
              methods=['DELETE'])
    @require_capability('case.manage')
    def operator_case_milestone_delete(milestone_id):
        return run_write(content_db.delete_case_milestone, milestone_id)

    # ---- 来源 ----

    @bp.route('/api/operator/cases/<int:case_id>/sources', methods=['GET'])
    @require_capability('case.manage')
    def operator_case_sources(case_id):
        return ok(sources=content_db.get_case_sources(case_id))

    @bp.route('/api/operator/cases/<int:case_id>/sources', methods=['POST'])
    @require_capability('case.manage')
    def operator_case_source_create(case_id):
        data = json_body()
        title = _text(data.get('title'), _MAX_TITLE)
        if not title:
            return fail(u'来源标题不能为空', 400)
        fields = _fields(data, ('title', 'media', 'date', 'url'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        fields.pop('title', None)
        return run_write(content_db.create_case_source, case_id, title, **fields)

    @bp.route('/api/operator/cases/sources/<int:source_id>', methods=['PUT'])
    @require_capability('case.manage')
    def operator_case_source_update(source_id):
        data = json_body()
        fields = _fields(data, ('title', 'media', 'date', 'url'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(content_db.update_case_source, source_id, **fields)

    @bp.route('/api/operator/cases/sources/<int:source_id>', methods=['DELETE'])
    @require_capability('case.manage')
    def operator_case_source_delete(source_id):
        return run_write(content_db.delete_case_source, source_id)

    # ---- 借鉴点 ----

    @bp.route('/api/operator/cases/<int:case_id>/lessons', methods=['GET'])
    @require_capability('case.manage')
    def operator_case_lessons(case_id):
        return ok(lessons=content_db.get_case_lessons(case_id))

    @bp.route('/api/operator/cases/<int:case_id>/lessons', methods=['POST'])
    @require_capability('case.manage')
    def operator_case_lesson_create(case_id):
        data = json_body()
        text = _text(data.get('text'))
        if not text:
            return fail(u'借鉴点不能为空', 400)
        fields = {}
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(content_db.create_case_lesson, case_id, text, **fields)

    @bp.route('/api/operator/cases/lessons/<int:lesson_id>', methods=['PUT'])
    @require_capability('case.manage')
    def operator_case_lesson_update(lesson_id):
        data = json_body()
        fields = {}
        if 'text' in data:
            fields['text'] = _text(data.get('text'))
        if 'sort_order' in data:
            fields['sort_order'] = _optional_int(data.get('sort_order')) or 0
        return run_write(content_db.update_case_lesson, lesson_id, **fields)

    @bp.route('/api/operator/cases/lessons/<int:lesson_id>', methods=['DELETE'])
    @require_capability('case.manage')
    def operator_case_lesson_delete(lesson_id):
        return run_write(content_db.delete_case_lesson, lesson_id)


OPERATOR_CASES_ROUTES = (
    ('/api/operator/cases', 'GET'),
    ('/api/operator/cases', 'POST'),
    ('/api/operator/cases/<int:case_id>', 'PUT'),
    ('/api/operator/cases/<int:case_id>', 'DELETE'),
    ('/api/operator/cases/<int:case_id>/stats', 'GET'),
    ('/api/operator/cases/<int:case_id>/stats', 'POST'),
    ('/api/operator/cases/stats/<int:stat_id>', 'PUT'),
    ('/api/operator/cases/stats/<int:stat_id>', 'DELETE'),
    ('/api/operator/cases/<int:case_id>/milestones', 'GET'),
    ('/api/operator/cases/<int:case_id>/milestones', 'POST'),
    ('/api/operator/cases/milestones/<int:milestone_id>', 'PUT'),
    ('/api/operator/cases/milestones/<int:milestone_id>', 'DELETE'),
    ('/api/operator/cases/<int:case_id>/sources', 'GET'),
    ('/api/operator/cases/<int:case_id>/sources', 'POST'),
    ('/api/operator/cases/sources/<int:source_id>', 'PUT'),
    ('/api/operator/cases/sources/<int:source_id>', 'DELETE'),
    ('/api/operator/cases/<int:case_id>/lessons', 'GET'),
    ('/api/operator/cases/<int:case_id>/lessons', 'POST'),
    ('/api/operator/cases/lessons/<int:lesson_id>', 'PUT'),
    ('/api/operator/cases/lessons/<int:lesson_id>', 'DELETE'),
)

__all__ = ['register_cases_routes', 'OPERATOR_CASES_ROUTES', 'CAPABILITIES_USED']
