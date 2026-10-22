# -*- coding: utf-8 -*-
"""农业培训域路由：农事日历、农产品目录、作物订阅与到期提醒。

从 app.py 迁出（后端按领域拆分 T10），URL、请求响应结构、状态码、错误码保持不变。

三条订阅/提醒路由都只认会话头 X-Session-Id，未登录一律 401；停用作物不可订阅、
不再推送、也打不开日历，三个接口同一口径，否则订阅后点进通知是 404。

会话取用户走共享层 core.session，数据访问走 database，本域不持有第二份会话实现。

为什么这里不新建 Blueprint：一个领域一个蓝图（见 docs/adr/0001），本域因单文件
600 行上限（spec 验收门槛）拆成两个路由模块，蓝图对象仍只有一个，定义在 routes.py，
这里复用它继续挂路由。农技问答与追问建议同在 routes.py。
"""

import logging
from datetime import datetime

from flask import jsonify, request


from core.session import get_session_user
from domains.agriculture.routes import agriculture_bp
from shared.review_freshness import is_review_current
from shared.solar_terms import solar_terms_of_month
from db_domains import farming, notifications
# 本域读 farming（公开），并在农事提醒到期时写 notification。写别人的域要显式
# 声明，让 tools/check_architecture.py 有据可判，也让「谁在给全员发通知」可查。
CAPABILITIES_USED = ('farming.read', 'notification.read')

logger = logging.getLogger(__name__)


@agriculture_bp.route('/api/agriculture/products', methods=['GET'])
def get_products():
    """农产品目录：读 farming_products 表（is_active=1，按 sort_order 排序）。

    返回结构与内容落库前保持一致（desc 由 summary 映射）。表读空就是空列表，
    不再回退硬编码目录（REFACTOR-PLAN 4.2）：退回半份数据会让「平台只有 8 个作物」
    这件事在界面上看不出来，而运营看不到的目录等于不存在。
    """
    try:
        rows = farming.get_farming_products()
    except Exception as e:
        logger.warning('读取农产品目录失败: %s', e)
        rows = []
    products = [{
        "id": r["id"],
        "name": r["name"],
        "icon": r.get("icon") or "seedling",
        "desc": r.get("summary") or "",
    } for r in rows]
    return jsonify({"success": True, "products": products})


@agriculture_bp.route('/api/agriculture/calendar/<product_id>', methods=['GET'])
def get_farming_calendar(product_id):
    """农时日历（年周期模板）。

    query:
      year   可选，缺省取服务器当前年
      month  可选，1-12；传 0 视为 0-indexed 的一月（兼容旧调用）；缺省取当前月
    """
    product = farming.get_farming_product(product_id)
    if not product or not product.get('is_active', 1):
        return jsonify({"success": False, "message": "未找到该农产品信息"}), 404

    now = datetime.now()
    try:
        year = int(request.args.get('year') or now.year)
    except (TypeError, ValueError):
        year = now.year

    raw_month = request.args.get('month')
    if raw_month is None or raw_month == '':
        month = now.month
    else:
        try:
            month = int(raw_month)
        except (TypeError, ValueError):
            month = now.month
        if month == 0:
            month = 1          # 0-indexed 兼容
        if month < 1 or month > 12:
            month = now.month

    phases = farming.get_farming_phenophases(product_id)
    tasks = farming.get_farming_tasks(product_id, month=month)
    labels = farming.get_farming_category_labels()
    source_map = farming.get_farming_source_map()

    # 物候期：标记当月命中项，并给出「当前物候期」（取首个命中项）
    phase_current = None
    for ph in phases:
        ph['in_month'] = farming.month_in_phase(month, ph['start_month'], ph['end_month'])
        if ph['in_month'] and phase_current is None:
            phase_current = ph

    # 节气：复用 Meeus 算法结果，day 预拆好供前端直接索引
    solar = [{"date": t["date"], "day": t["day"], "name": t["name"]}
             for t in solar_terms_of_month(year, month)]

    # 任务：MM-DD 拆出 date/day；task_md 为空则 day/date 均为 null（前端归入「本月内」）
    out_tasks = []
    for t in tasks:
        md = t.get('task_md')
        verified = int(t.get('is_verified') or 0)
        if verified and not is_review_current(t.get('verified_at')):
            verified = 0
        src = source_map.get(t.get('source_key') or '')
        day = None
        date = None
        if md:
            try:
                mm, dd = md.split('-')
                day = int(dd)
                date = '%04d-%s' % (year, md) if int(mm) == month else None
                if date is None:
                    day = None
            except (ValueError, AttributeError):
                day = None
        out_tasks.append({
            "id": t["id"],
            "date": date,
            "day": day,
            "task_md": md,
            "title": t["title"],
            "category": t["category"],
            "category_label": labels.get(t["category"], t["category"]),
            "priority": t.get("priority") or "medium",
            "icon": t.get("icon") or "tasks",
            "description": t.get("description") or "",
            "tip": t.get("tip") or "",
            "phase_id": t.get("phase_id"),
            "phase_name": t.get("phase_name"),
            "phase_color": t.get("phase_color"),
            "sort_order": t.get("sort_order", 0),
            # 日期是否已由农技人员复核：0 表示按农时规律推算的参考值（前端加「约」并挂提示条）
            "is_verified": verified,
            # evidence_level：verified（已人工复核）/ sourced（有公开技术资料依据，待核）
            #                 / unsourced（无来源登记，不应出现）
            "evidence_level": ("verified" if verified
                               else ("sourced" if src else "unsourced")),
            # 该日期的农艺依据（为什么定在这个时间），供前端展开给用户看
            "date_basis": t.get("date_basis") or "",
            # 来源方向：机构 + 文件类型；doc_no 多为「待核」
            "source": ({
                "key": src.get("key"),
                "name": src.get("name") or "",
                "org": src.get("org") or "",
                "doc_type": src.get("doc_type") or "",
                "doc_no": src.get("doc_no") or "",
                "url": src.get("url") or "",
            } if src else None),
        })

    # 只要存在「有日期但未复核」的任务，就向前端声明本月日期为推算参考值
    dates_provisional = any(t["day"] and not t["is_verified"] for t in out_tasks)

    # 本月数据底账：让前端能如实说明「依据什么编排、还有多少条待农技复核」
    sourced_keys = []
    for t in out_tasks:
        k = (t.get("source") or {}).get("key")
        if k and k not in sourced_keys:
            sourced_keys.append(k)
    source_summary = {
        "total": len(out_tasks),
        "verified": sum(1 for t in out_tasks if t["evidence_level"] == "verified"),
        "sourced": sum(1 for t in out_tasks if t["evidence_level"] == "sourced"),
        "unsourced": sum(1 for t in out_tasks if t["evidence_level"] == "unsourced"),
        "sources": [{
            "key": source_map[k]["key"],
            "name": source_map[k]["name"],
            "org": source_map[k].get("org") or "",
            "doc_type": source_map[k].get("doc_type") or "",
            "doc_no": source_map[k].get("doc_no") or "",
            "url": source_map[k].get("url") or "",
        } for k in sourced_keys],
    }

    # 该作物全年用到的来源集合（供「数据依据」说明面板一次列全，避免逐月变动）
    year_keys = []
    try:
        for t in farming.get_farming_tasks(product_id):
            k = t.get('source_key') or ''
            if k and k in source_map and k not in year_keys:
                year_keys.append(k)
    except Exception as e:
        logger.warning('收集作物全年来源失败: %s', e)
    sources_all = [{
        "key": source_map[k]["key"],
        "name": source_map[k]["name"],
        "org": source_map[k].get("org") or "",
        "doc_type": source_map[k].get("doc_type") or "",
        "doc_no": source_map[k].get("doc_no") or "",
        "url": source_map[k].get("url") or "",
    } for k in year_keys]

    return jsonify({
        "success": True,
        "product": {
            "id": product["id"], "name": product["name"],
            "icon": product.get("icon") or "seedling",
        },
        "year": year,
        "month": month,
        "is_configured": bool(tasks or phases),
        "dates_provisional": dates_provisional,
        "source_summary": source_summary,
        "sources_all": sources_all,
        "phenophase_current": ({
            "id": phase_current["id"],
            "name": phase_current["name"],
            "color": phase_current.get("color"),
            "description": phase_current.get("description") or "",
        } if phase_current else None),
        "phenophases": [{
            "id": ph["id"], "name": ph["name"],
            "start_month": ph["start_month"], "end_month": ph["end_month"],
            "color": ph.get("color"), "description": ph.get("description") or "",
            "in_month": ph["in_month"],
        } for ph in phases],
        "solar_terms": solar,
        "tasks": out_tasks,
    })


@agriculture_bp.route('/api/agriculture/subscriptions', methods=['GET'])
def get_my_farming_subscriptions():
    """当前用户订阅的作物列表"""
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    return jsonify({
        "success": True,
        "product_ids": farming.get_farming_subscriptions(user['username']),
    })


@agriculture_bp.route('/api/agriculture/subscribe', methods=['POST'])
def subscribe_farming():
    """订阅某作物的农事提醒（幂等）"""
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    data = request.get_json(silent=True) or {}
    pid = (data.get('product_id') or '').strip()
    if not pid:
        return jsonify({"success": False, "message": "缺少 product_id"}), 400
    _p = farming.get_farming_product(pid)
    if not _p or not _p.get('is_active', 1):
        # 与 /api/agriculture/calendar/<id> 保持一致：停用作物不可订阅，避免订阅后无日历可看
        return jsonify({"success": False, "message": "未找到该农产品信息"}), 404
    farming.set_farming_subscription(user['username'], pid, True)
    return jsonify({
        "success": True, "subscribed": True,
        "product_ids": farming.get_farming_subscriptions(user['username']),
    })


@agriculture_bp.route('/api/agriculture/subscribe/<product_id>', methods=['DELETE'])
def unsubscribe_farming(product_id):
    """取消订阅（幂等）"""
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401
    farming.set_farming_subscription(user['username'], product_id, False)
    # 同步清理当期提醒日志：否则「退订 → 当月重新订阅」会因幂等键命中而静默收不到提醒
    farming.clear_farming_reminder_log(user['username'], product_id)
    return jsonify({
        "success": True, "subscribed": False,
        "product_ids": farming.get_farming_subscriptions(user['username']),
    })


@agriculture_bp.route('/api/agriculture/reminders/check', methods=['POST'])
def check_farming_reminders():
    """登录时补发农事提醒。

    对每个订阅作物，若当期（YYYY-MM）尚未推送过，则生成一条站内通知并记录日志。
    幂等：同一用户 + 同一作物 + 同一月份只发一次。

    取「已到期」任务（task_md 的日 <= 今天），避免在月初就预告整月的未来农事；
    若今天尚无到期任务，则不发送、也不写日志，用户下次登录会在此后的日期正常收到。
    """
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401

    uid = user['username']
    now = datetime.now()
    period = '%04d-%02d' % (now.year, now.month)
    sent, details = 0, []

    for pid in farming.get_farming_subscriptions(uid):
        if farming.has_farming_reminder_sent(uid, pid, period):
            continue
        product = farming.get_farming_product(pid)
        # 与 /api/agriculture/calendar/<id> 一致：停用作物不再推送（否则点进通知是 404）
        if not product or not product.get('is_active', 1):
            continue
        due = farming.get_due_farming_tasks(pid, now.year, now.month, until_day=now.day)
        if not due:
            continue
        # 文案带具体日期：优先高优先级，最多 3 条
        picked = [t for t in due if t.get('priority') == 'high'][:3] or due[:3]
        highlights = [farming.farming_task_brief(t) for t in picked]
        title = '%d月%s农事提醒' % (now.month, product['name'])
        content = '本月已到期农事：' + '、'.join(highlights) + '。详情见「农业技能 · 农时智能日历」。'
        try:
            notifications.create_notification(uid, 'farming_reminder', title, content, 'farming', pid)
        except Exception as e:
            logger.warning('农事提醒写入通知失败(%s/%s): %s', uid, pid, e)
            continue
        farming.mark_farming_reminder_sent(uid, pid, period)
        sent += 1
        details.append({
            "product_id": pid, "product_name": product['name'],
            "period": period, "title": title,
            "items": [t['task_md'] for t in picked],
        })

    return jsonify({"success": True, "period": period, "sent": sent, "details": details})


__all__ = []
