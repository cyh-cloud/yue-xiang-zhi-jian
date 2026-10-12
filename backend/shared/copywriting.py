# -*- coding: utf-8 -*-
"""文案实训评分（2026-10-05 走查 P1-2）：纯规则、可复现，不依赖 AI。

与直播话术的 /api/ecommerce/feedback 分开：文案评的是「结构/卖点/格式契合/合规」，
且长度上限按文案的 EC_COPY_MAX_LEN。打分依据逐项给出，让学员知道分从哪来。
"""

import re


def copy_score(text, fmt):
    """规则评分商品文案（0-100，四维）。可复现、无随机数。"""
    t = text or ''
    n = len(t)

    # ① 结构完整度：是否有标题/分点/换行分层
    has_heading = bool(re.search(r'(?:^|\n)\s*(?:##|###|【|\d{1,2}[.、])', t))
    has_multi_line = t.count('\n') >= 3
    structure = 50 + (20 if has_heading else 0) + (15 if has_multi_line else 0) + \
        min(10, t.count('\n') // 2)

    # ② 卖点具体度：命中的具体描述词越多分越高（避免空话）
    selling_kw = re.findall(r'甜|香|鲜|脆|嫩|糯|口感|风味|产地|直发|冷链|规格|新鲜|品质|果肉|核|汁', t)
    selling = 45 + min(len(set(selling_kw)) * 6, 40) + (15 if len(t) >= 120 else 0)

    # ③ 格式契合度：按所选格式的典型特征（主图短句 / 短视频时间轴 / 朋友圈 emoji 等）
    fmt_fit = 60
    if fmt == '主图文案':
        fmt_fit += 15 if re.search(r'\d{1,2}[.、]', t) else 0
        fmt_fit += 10 if len(t) < 300 else 0
    elif fmt == '短视频脚本':
        fmt_fit += 15 if re.search(r'\d+[-~]\d+\s*秒', t) else 0
    elif fmt == '朋友圈':
        fmt_fit += 10 if len(t) < 200 else 0
    elif fmt == '小红书':
        fmt_fit += 10 if re.search(r'#\S+|emoji|姐妹|家人们', t) else 0
    else:  # 详情页
        fmt_fit += 15 if re.search(r'(?:^|\n)\s*(?:##|###)', t) else 0
    fmt_fit = min(98, fmt_fit)

    # ④ 合规自检：残留【待填写】或绝对化用语扣分
    compliance = 100
    todo_count = t.count('【待填写')
    compliance -= min(todo_count * 6, 30)          # 未补真实信息扣分
    if re.search(r'全网最低|第一|最好|绝对|顶级|唯一', t):
        compliance -= 20                            # 绝对化用语扣分
    compliance = max(30, compliance)

    overall = round((structure + selling + fmt_fit + compliance) / 4)
    tips = []
    if todo_count:
        tips.append('还有 %d 处【待填写】没有换成真实信息' % todo_count)
    if re.search(r'全网最低|第一|最好|绝对|顶级|唯一', t):
        tips.append('避免「全网最低/第一/最好」等绝对化用语')
    if n < 80:
        tips.append('篇幅偏短，建议补充卖点与场景细节')
    return {
        "structure_score": min(98, structure),
        "selling_score": min(98, selling),
        "format_score": fmt_fit,
        "compliance_score": compliance,
        "overall_score": overall,
        "suggestions": (tips or ['结构完整、卖点具体，整体不错']) + ['评分由规则分析给出（可复现）'],
        "source": "rule",
        "source_note": "文案评分由规则分析给出（可复现，不含 AI 评分）"
    }


__all__ = ['copy_score']
