# -*- coding: utf-8 -*-
"""常见病虫害速查：按作物的条目查询与来源标注。

从 app.py 迁出（后端按领域拆分 T11），URL、请求响应结构、状态码、错误码保持不变。
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

    # 作物按钮上的计数是「该作物一共有多少条」，与 kind / q 两个筛选无关
    # （T12 才把它改成「当前筛选条件下该作物的条数」，本票不改对外语义）。
    per_crop_counts = {}
    for entry in pest.get_pest_entries(with_details=False):
        per_crop_counts[entry['crop']] = per_crop_counts.get(entry['crop'], 0) + 1

    entries = []
    for entry in pest.get_pest_entries(crop_id=crop or None):
        if kind and entry.get('kind') != kind:
            continue
        if keyword:
            blob = u' '.join([
                str(entry.get('disease') or u''),
                str(entry.get('alias') or u''),
                str(entry.get('pathogen') or u''),
                str(entry.get('crop_name') or u''),
                u' '.join(entry.get('symptoms') or []),
            ])
            if keyword not in blob:
                continue
        entries.append(pest_entry_view(entry))

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
        "stats": pest.get_pest_stats(),
        "disclaimer": PEST_DISCLAIMER,
    }), 200


def read_pest_knowledge():
    u"""速查主流程。数据量很小（数十条），一次取回由前端本地筛选。"""
    crop = (request.args.get('crop') or u'').strip()
    kind = (request.args.get('kind') or u'').strip()
    keyword = (request.args.get('q') or u'').strip()
    return list_pest_entries(crop=crop, kind=kind, keyword=keyword)


__all__ = ['PEST_DISCLAIMER', 'pest_entry_view', 'list_pest_entries', 'read_pest_knowledge']
