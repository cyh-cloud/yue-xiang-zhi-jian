# -*- coding: utf-8 -*-
"""常见病虫害速查：按作物的条目查询与来源标注。

T12 起筛选与分页全在服务端做，前端只负责渲染。
URL、请求响应结构、状态码、错误码保持不变（T11 从 app.py 迁出）。

对外形状（ADR 0002 记录的唯一一处接口变化）：
  · 仍接 crop / kind / q 三个筛选参数，语义不变；
  · 新增 limit / offset，默认每页 50 条；
  · 响应新增 total（筛选后总条数）；
  · crops[].count 改为「当前筛选条件下该作物的条数」，与按钮点下去看到的一致。
其余（卡片字段、详情字段、disclaimer、stats、空态与错误态措辞、状态码、错误码）不变。
T07 起内容改读 pest 域的五张表（db_domains.pest），不再读代码常量。
诊断的知识库降级与速查仍是同一份知识的两个视图，只是事实源从代码常量变成了库。

速查定位是「只读参考」，不做任何推断：来源资料没给出的数值（尤其是安全间隔期）
如实留空并由界面显示「未提供」，不用一个看起来合理的数字把空白填上。
"""

from flask import jsonify, request

from db_domains import pest

PEST_DISCLAIMER = (
    u'本速查整理自省、市、县农业农村部门公开发布的病虫情报、防控技术指引与农药登记数据，'
    u'仅供学习与参考。农药的实际用药量、安全间隔期与每季最多使用次数，'
    u'一律以你所购农药标签标注为准；资料中未给出安全间隔期的药剂，请勿自行推算。'
    u'标注「暂无实拍图」的条目表示尚未取得可用的授权照片，界面上不会用示意图冒充真实病征。'
)


# 分页参数。默认每页 50 条：当前 45 条一次拿完，数据涨上去之后首屏不会一次传成百上千条。
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

# 分页参数不合法时的错误文案，与 crop / kind 两支错误同口径（400 + code + message），
# 前端拿到 code 就能与「作物不认识」区分开，不必去匹配中文。
PAGINATION_ERROR = (u'分页参数不合法：limit 需为 1 到 %d 的整数，'
                    u'offset 需为不小于 0 的整数' % MAX_PAGE_SIZE)


def _pagination_error():
    return jsonify({
        "success": False, "code": "bad_request", "message": PAGINATION_ERROR
    }), 400


def _parse_pagination():
    u"""解析 limit / offset。返回 (limit, offset, 错误响应)；合法时第三项为 None。

    非整数、越界、负数一律 400，不静默取默认值：前端把 NaN 或用户手改的
    ?limit=9999 拼上来时，默默兜底会让人以为参数生效了，翻页永远对不上。
    """
    limit_raw = (request.args.get('limit') or u'').strip()
    offset_raw = (request.args.get('offset') or u'').strip()
    try:
        limit = int(limit_raw) if limit_raw else DEFAULT_PAGE_SIZE
        offset = int(offset_raw) if offset_raw else 0
    except ValueError:
        return None, None, _pagination_error()
    if limit < 1 or limit > MAX_PAGE_SIZE or offset < 0:
        return None, None, _pagination_error()
    return limit, offset, None

def pest_entry_view(entry):
    u"""把一条病虫害记录整理成对外结构（不做推断，缺什么就缺什么）。

    输入是 db_domains.pest.get_pest_entries() 的一条，那里已经把作物层与来源层
    拼好了（crop / crop_name / crop_icon / sources / image），这里只做「视图」这一层：
    缺的字段按空值给出，不补内容。
    """
    return {
        u'id': entry.get('id'),
        u'crop': entry.get('crop'),
        u'crop_name': entry.get('crop_name'),
        u'crop_icon': entry.get('crop_icon'),
        u'disease': entry.get('disease'),
        u'alias': entry.get('alias') or u'',
        u'kind': entry.get('kind'),
        u'pathogen': entry.get('pathogen') or u'',
        u'part': entry.get('part') or u'',
        u'severity': entry.get('severity') or u'',
        u'symptoms': entry.get('symptoms') or [],
        u'occurrence': entry.get('occurrence') or u'',
        u'treatment': entry.get('treatment') or [],
        u'prevention': entry.get('prevention') or [],
        u'registered': entry.get('registered') or [],
        u'chem_table': entry.get('chem_table') or [],
        u'safety_note': entry.get('safety_note') or u'',
        # 无授权实拍图时明确为 None，前端据此显示「暂无实拍图」占位。
        u'image': entry.get('image'),
        u'sources': entry.get('sources') or [],
        u'is_verified': int(entry.get('is_verified') or 0),
    }


def list_pest_entries(crop=u'', kind=u'', keyword=u''):
    u"""按作物、类型与关键词筛选条目。返回 (响应体, 状态码)。"""
    crops = pest.get_pest_crops()
    if crop and crop not in [c['id'] for c in crops]:
        return jsonify({
            "success": False, "code": "unknown_crop",
            "message": u"暂不支持该作物，请从列表中选择"
        }), 400
    if kind and kind not in ('disease', 'pest'):
        return jsonify({
            "success": False, "code": "bad_request",
            "message": u"类型筛选仅支持 disease 或 pest"
        }), 400

    # 作物按钮上的计数是「当前筛选条件下该作物的条数」，与按钮天然一致：
    # 点下去看到的就是这个数。kind / q 两个筛选会同时改变每个作物的计数，
    # 否则切到「虫害」时按钮还显示该作物全部条目数，点过去条数对不上。
    per_crop_counts = {}
    for entry in pest.get_pest_entries(with_details=False):
        if kind and entry.get('kind') != kind:
            continue
        if keyword and not _matches_keyword(entry, keyword):
            continue
        per_crop_counts[entry['crop']] = per_crop_counts.get(entry['crop'], 0) + 1

    limit, offset, error = _parse_pagination()
    if error:
        return error

    # total 必须是筛选后总条数，所以先把整批筛完再切片，不能边筛边截。
    matched = []
    for entry in pest.get_pest_entries(crop_id=crop or None):
        if kind and entry.get('kind') != kind:
            continue
        if keyword and not _matches_keyword(entry, keyword):
            continue
        matched.append(entry)

    entries = [pest_entry_view(entry) for entry in matched[offset:offset + limit]]

    return jsonify({
        "success": True,
        "crops": [{
            u'id': c['id'],
            u'name': c['name'],
            u'icon': c['icon'],
            u'summary': c['summary'] or u'',
            u'count': per_crop_counts.get(c['id'], 0),
        } for c in crops],
        "entries": entries,
        "total": len(matched),
        "stats": pest.get_pest_stats(),
        "disclaimer": PEST_DISCLAIMER,
    }), 200


def _matches_keyword(entry, keyword):
    u"""关键词命中判定：病名、别名、病原、作物名与症状文本里出现过就算。

    与切换前前端 pestGuideMatches() 的本地筛选同一口径，只是搬到服务端。
    """
    blob = u' '.join([
        str(entry.get('disease') or u''),
        str(entry.get('alias') or u''),
        str(entry.get('pathogen') or u''),
        str(entry.get('crop_name') or u''),
        u' '.join(entry.get('symptoms') or []),
    ])
    return keyword in blob


def read_pest_knowledge():
    u"""速查主流程。筛选与分页都在服务端做，前端只渲染结果。"""
    crop = (request.args.get('crop') or u'').strip()
    kind = (request.args.get('kind') or u'').strip()
    keyword = (request.args.get('q') or u'').strip()
    return list_pest_entries(crop=crop, kind=kind, keyword=keyword)


__all__ = ['PEST_DISCLAIMER', 'pest_entry_view', 'list_pest_entries', 'read_pest_knowledge']
