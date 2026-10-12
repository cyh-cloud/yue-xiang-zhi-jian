# -*- coding: utf-8 -*-
"""常见病虫害速查：按作物的条目查询与来源标注。

从 app.py 迁出（后端按领域拆分 T11），URL、请求响应结构、状态码、错误码保持不变。

与诊断共用同一份 domain_data.pest_diagnosis.pest_data：诊断的知识库降级读
common_diseases 的病名与症状，速查读全部富字段。两者是同一份事实源的两个视图，
所以同属一个领域路由目录（见 domains/pest/__init__.py）。

速查定位是「只读参考」，不做任何推断：来源资料没给出的数值（尤其是安全间隔期）
如实留空并由界面显示「未提供」，不用一个看起来合理的数字把空白填上。
"""

from flask import jsonify, request

from domain_data.pest_diagnosis.pest_data import (
    PEST_CROP_ORDER,
    PEST_KNOWLEDGE,
    PEST_SOURCE_MAP,
    get_pest_stats,
    iter_pest_entries,
)

PEST_DISCLAIMER = (
    '本速查整理自省、市、县农业农村部门公开发布的病虫情报、防控技术指引与农药登记数据，'
    '仅供学习与参考。农药的实际用药量、安全间隔期与每季最多使用次数，'
    '一律以你所购农药标签标注为准；资料中未给出安全间隔期的药剂，请勿自行推算。'
    '标注「暂无实拍图」的条目表示尚未取得可用的授权照片，界面上不会用示意图冒充真实病征。'
)


def pest_entry_view(entry, crop, crop_data):
    """把一条病虫害记录整理成对外结构（不做推断，缺什么就缺什么）。"""
    return {
        'id': entry.get('id'),
        'crop': crop,
        'crop_name': crop_data.get('name'),
        'crop_icon': crop_data.get('icon'),
        'disease': entry.get('disease'),
        'alias': entry.get('alias') or '',
        'kind': entry.get('kind'),
        'pathogen': entry.get('pathogen') or '',
        'part': entry.get('part') or '',
        'severity': entry.get('severity') or '',
        'symptoms': entry.get('symptoms') or [],
        'occurrence': entry.get('occurrence') or '',
        'treatment': entry.get('treatment') or [],
        'prevention': entry.get('prevention') or [],
        'registered': entry.get('registered') or [],
        'chem_table': entry.get('chem_table') or [],
        'safety_note': entry.get('safety_note') or '',
        # 无授权实拍图时明确为 None，前端据此显示「暂无实拍图」占位。
        'image': entry.get('image'),
        'sources': [PEST_SOURCE_MAP[k] for k in (entry.get('sources') or [])
                    if k in PEST_SOURCE_MAP],
        'is_verified': int(entry.get('is_verified') or 0),
    }


def list_pest_entries(crop='', kind='', keyword=''):
    """按作物、类型与关键词筛选条目。返回 (响应体, 状态码)。"""
    if crop and crop not in PEST_KNOWLEDGE:
        return jsonify({
            "success": False, "code": "unknown_crop",
            "message": "暂不支持该作物，请从列表中选择"
        }), 400
    if kind and kind not in ('disease', 'pest'):
        return jsonify({
            "success": False, "code": "bad_request",
            "message": "类型筛选仅支持 disease 或 pest"
        }), 400

    entries = []
    for c, crop_data, entry in iter_pest_entries():
        if crop and c != crop:
            continue
        if kind and entry.get('kind') != kind:
            continue
        if keyword:
            blob = ' '.join([
                str(entry.get('disease') or ''),
                str(entry.get('alias') or ''),
                str(entry.get('pathogen') or ''),
                str(crop_data.get('name') or ''),
                ' '.join(entry.get('symptoms') or []),
            ])
            if keyword not in blob:
                continue
        entries.append(pest_entry_view(entry, c, crop_data))

    crops = []
    for c in PEST_CROP_ORDER:
        cd = PEST_KNOWLEDGE.get(c)
        if not cd:
            continue
        crops.append({
            'id': c,
            'name': cd.get('name'),
            'icon': cd.get('icon'),
            'summary': cd.get('summary') or '',
            'count': len(cd.get('common_diseases') or []),
        })

    return jsonify({
        "success": True,
        "crops": crops,
        "entries": entries,
        "stats": get_pest_stats(),
        "disclaimer": PEST_DISCLAIMER,
    }), 200


def read_pest_knowledge():
    """速查主流程。数据量很小（数十条），一次取回由前端本地筛选。"""
    crop = (request.args.get('crop') or '').strip()
    kind = (request.args.get('kind') or '').strip()
    keyword = (request.args.get('q') or '').strip()
    return list_pest_entries(crop=crop, kind=kind, keyword=keyword)


__all__ = ['PEST_DISCLAIMER', 'pest_entry_view', 'list_pest_entries', 'read_pest_knowledge']
