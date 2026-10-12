# -*- coding: utf-8 -*-
"""电商运营域路由：带货话术、商品文案、客服对练三条链路。

从 app.py 迁出（后端按领域拆分 T12），URL、请求响应结构、状态码、错误码保持不变。
本域在 `/api/ecommerce/*` 前缀下只负责这三条链路；朗读实录分析、三类实训提交与
记录查询属直播实训域（T13），不在本文件。

三条链路的共有口径：

- 上游未配置 / 不可用时，**生成类**接口走可见降级（EC5）：200 + degraded:true + 带正文，
  前端据此告知学员「这次不是 AI 生成的」，绝不静默返回 success:True 冒充 AI。
- 评分类接口（话术评分 / 文案评分）不调用上游，纯规则、可复现（EC2）。
- 宣传合规口径 _EC_PROMO_RULE（EC1）只进**生成类**提示词；评分与客服提示不承载它。
  认证与检测数据不得编造、不使用绝对化用语、不虚构价格与优惠这条红线，
  既约束模型输出，也约束本域的兜底文案。
- 作物白名单只对生成类接口的作物字段生效；客服对练的产品是自由文本
  （学员可自填，如「增城桂味荔枝」），只做非空 + 限长，避免 prompt 注入面。
- 限流走共享层 core.session，上游调用一律走共享层 ai.client，本域不持有第二份实现。

作物白名单与校验函数在共享层 shared.ec_products，
直播实训域与电商域都从共享层取，全站只有一份作物表。
"""

import json
import logging
import re

from flask import Blueprint, jsonify, request

from ai.client import (
    AI_REASONING_TOKEN_RESERVE,
    call_ai_service,
    chat_completion,
    chat_model,
)
from core.session import client_key, rate_limited
from domains.ecommerce.copy_fallback import generate_fallback_copywriting
from domains.ecommerce.feedback_rules import analyze_script, generate_suggestions
from domains.ecommerce.prompts import (
    EC_COPY_FORMAT_PROMPTS,
    EC_COPY_FORMATS,
    EC_COPY_MAX_LEN,
    EC_CS_DIFFICULTY_PROMPTS,
    EC_CS_NEXT_FALLBACKS,
    EC_CS_PERSONALITIES,
    EC_CS_SCENARIOS,
    EC_PRODUCTS,
    EC_RATE_COMMENTS_LIMIT,
    EC_RATE_COPY_LIMIT,
    EC_RATE_CS_AUX_LIMIT,
    EC_RATE_CS_LIMIT,
    EC_RATE_FEEDBACK_LIMIT,
    EC_RATE_SCRIPT_LIMIT,
    EC_SCRIPT_MAX_LEN,
    EC_STYLE_KEYS,
    EC_STYLE_PROMPTS,
    _EC_PROMO_RULE,
)
from domains.ecommerce.service_rules import (
    _sentiment_from_score,
    analyze_service_reply,
    generate_dynamic_fallback,
    generate_dynamic_hint,
)
from shared.copywriting import copy_score
from shared.ec_products import ec_product_ok

logger = logging.getLogger(__name__)

ecommerce_bp = Blueprint('ecommerce', __name__)


# ==================== 带货话术 ====================

@ecommerce_bp.route('/api/ecommerce/script', methods=['POST'])
def generate_script():
    data = request.get_json() or {}
    product = str(data.get('product', '') or '').strip() or u'荔枝'
    style = str(data.get('style', '') or '').strip() or u'热情'

    # EC6：本接口此前没有任何限流，而它同样调用上游、且走的是推理模型。
    if rate_limited('ec-script:' + client_key(), EC_RATE_SCRIPT_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": u"请求过于频繁，请稍后再试"}), 429
    # EC9：未知风格前，先按默认值兜底（缺省/空串视为「热情」），明确拒绝不认识的风格
    if style not in EC_STYLE_KEYS:
        return jsonify({"success": False, "code": "unknown_style",
                        "message": u"不支持的话术风格，请从列表中选择"}), 400
    # EC9：product 缺省时为粤语特色农产品，按荔枝兜底；给了不认识的作物则明确拒绝
    if not ec_product_ok(product):
        return jsonify({"success": False, "code": "unknown_product",
                        "message": u"暂不支持该农产品，请从列表中选择"}), 400

    style_config = EC_STYLE_PROMPTS.get(style, EC_STYLE_PROMPTS[u'热情'])
    techniques_text = '\n'.join(u'- %s' % t for t in style_config['techniques'])
    try:
        ai_script = call_ai_service(
            system_prompt=u"""你是一位资深直播带货主播，擅长为广东特色农产品设计直播话术。

你的风格：%s

话术技巧：
%s

话术结构要求：
1. 开场吸睛（1-2句）：用3秒钩子抓住观众注意力
2. 产品介绍（2-3句）：突出卖点（产地、口感、新鲜度，不确定处写【待填写】）
3. 信任背书（1-2句）：描述/品牌/用户口碑，**不确定的信息写【待填写】，不要编造**
4. 促单转化（1-2句）：制造紧迫感（限时/库存），价格与优惠写【待填写】
5. 互动引导（1句）：引导点赞/关注/下单

其他要求：
- 总长度8-12句话，每句一行
- 语言要地道、有乡土气息、口语化
- 适当加入关键词标签，不要过度堆砌
- 使用行动指令（如扣1、点击链接）

%s""" % (style_config['desc'], techniques_text, _EC_PROMO_RULE),
            user_message=u"为广东%s设计一段直播带货话术，要突出产品特色和卖点" % product,
            model=chat_model()
        )
        return jsonify({"success": True, "script": ai_script})
    except Exception as e:
        logger.error(u"话术生成失败: %s", e)
        # EC5：降级必须可见。AI 不可用时，如果是产品相关失败就降级为规则话术；
        # 若产品本身不被支持，则明确报错。
        # 同时按 EC1 的要求，话术里的认证、检测数据、价格优惠一律写占位符，
        # 不编造任何具体承诺。
        fallback_scripts = {
            u'热情': u"""家人们，看过来！这是从广东产地直发的%s！
(停顿) 想要的点个关注，我给大家详细介绍
这是正宗优质农产品，口感和品质都没得说
下单前：【待填写：真实价格与优惠】，优惠以店铺实际活动为准
(停顿) 想要的扣1，我给大家争取福利
懂行的都知道，产地直发的新鲜程度就是不一样
【待填写：品种、产地等真实信息】
现在下单，享【待填写：按店铺实际活动填写】
(停顿) 错过这次，再等一年
赶紧点击下方链接，手慢无！""" % product,

            u'专业': u"""各位朋友，大家好。今天给大家介绍广东特产%s。
这款产品来自广东优质产区，品质有保障。
每一批都经过严格筛选，具体规格与【待填写：检测项目】以实物与报告为准。
与同类产品相比，产地直发，少了中间环节。
关于认证信息：【待填写：认证名称，不确定就不要写】
不同品种的选购与食用方式各有不同，我给大家详细讲解。
【待填写：保存与食用建议】
性价比很高，具体优惠以本店当前活动为准。
喜欢的可以直接下单，有问题随时问我。""" % product,

            u'故事': u"""在广东的一个小村庄里，%s的故事已经延续了很多年。
这里的风土人情，养成了它独特的口感。
"小时候，每到季节，长辈们就会摘最新鲜的果子"
(停顿) 每一颗都承载着农人的心血
从枝头到您的手中，经过【待填写：采摘与发货时效】
这份来自岭南的味道，值得您试一试
现在当季的%s正是口感最好的时候
想要回味这份乡愁的朋友，可以下单尝一尝
(停顿) 数量有限，售完即止""" % (product, product),

            u'高级': u"""此刻，为您呈现来自岭南的%s。
【待填写：按实际外观描述】，从广东产地直发。
细节之处见品质，包装与规格请见【待填写：真实信息】。
我们相信，好的产品会自己说话。
不必过多渲染，【待填写：品种与等级】足以说明一切。
适合追求品质生活的您，也适合【待填写：真实送礼场景】。
关于价格与权益，请以店铺当前页面为准。
感兴趣的朋友，可以慢慢了解。
品质之选，值得细细品味""" % product
        }
        return jsonify({"success": True, "degraded": True,
                        "script": fallback_scripts.get(style, fallback_scripts[u'热情'])})


# ==================== 话术评分 ====================

@ecommerce_bp.route('/api/ecommerce/feedback', methods=['POST'])
def get_live_feedback():
    """评一段直播带货话术稿的质量。

    口径说明（2026-10-05，EC2/EC3）：这里评的是**送进来的稿子**；EC3 之后前端改为提交
    「学员自己的稿」。另新增 `/api/ecommerce/live/report` 度量学员的**现场朗读表现**，
    两者是不同对象，不要混为一谈。
    """
    data = request.get_json() or {}
    script_text = str(data.get('script', '') or '')

    # EC6：本接口此前无任何限流、无输入上限（实测匿名连打 8 次全部 200）。
    if rate_limited('ec-feedback:' + client_key(), EC_RATE_FEEDBACK_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": u"请求过于频繁，请稍后再试"}), 429
    if not script_text.strip():
        return jsonify({"success": False, "code": "empty_script",
                        "message": u"请先写出或生成一段话术"}), 400
    if len(script_text) > EC_SCRIPT_MAX_LEN:
        return jsonify({"success": False, "code": "script_too_long",
                        "message": u"话术过长，请控制在 %d 字以内" % EC_SCRIPT_MAX_LEN}), 400

    try:
        # EC2：改走对话模型 `chat_model()`。此前留空 → 用默认推理模型 step-3.7-flash，
        # 其「思考」会吃掉 max_tokens，额度不够时正文为空 → 抛错 → 静默降级为规则分。
        # 这也正是实测 6 次里 3 次走 except 分支的原因（单次还要等 10s）。
        result = call_ai_service(
            system_prompt=u"""你是直播话术评分专家。分析以下直播带货话术，给出四个维度的评分和改进建议。

请先分析话术中的具体特征（互动词数量、感叹句数量、信息支撑等），然后给出评分。

评分维度（每项0-100整数，四个分数必须不同）：
- speed_score：文案节奏（**只看文本**：停顿标记、句子长短变化、朗读顺不顺；不代表实际语速）
- emotion_score：情绪感染力（看感叹句、情绪词、反问句）
- interaction_score：互动技巧（看"扣1""点赞""家人们"等互动词数量）
- selling_score：卖点提炼（看卖点是否清晰、【】标注是否到位）

注意：不要因为话术里出现【待填写】占位就扣分 —— 占位是刻意要求用户补真实信息的；
反过来，若话术里出现了无法核实的具体认证、检测数据或价格承诺，应在 summary 里提醒。

输出格式（严格JSON，不要其他文字）。每个维度必须同时给出 evidence ——
用一句话**引用或概括稿子里的原文**说明给分依据（不超过40字），让学员知道分从哪来：
{"speed_score":数字,"speed_evidence":"...","emotion_score":数字,"emotion_evidence":"...","interaction_score":数字,"interaction_evidence":"...","selling_score":数字,"selling_evidence":"...","summary":"20字总评","suggestions":["针对性建议1","建议2","建议3"]}""",
            user_message=u"请评分：\n%s" % script_text,
            model=chat_model()
        )
        try:
            json_match = re.search(r'\{.*?\}', result, re.DOTALL)
            feedback = json.loads(json_match.group()) if json_match else json.loads(result)
        except (json.JSONDecodeError, AttributeError, TypeError):
            feedback = {}

        # 用规则分析作为基础
        s, e, i, se = analyze_script(script_text)

        # 如果AI返回了有效分数且有差异，优先用AI的；否则用规则分析
        ai_scores = [feedback.get('speed_score'), feedback.get('emotion_score'),
                     feedback.get('interaction_score'), feedback.get('selling_score')]
        ai_valid = all(isinstance(x, (int, float)) and 40 <= x <= 100 for x in ai_scores)
        ai_diff = len(set(ai_scores)) >= 3  # 至少3个不同才算有效

        if ai_valid and ai_diff:
            final_speed, final_emotion, final_interaction, final_selling = [int(x) for x in ai_scores]
            final_suggestions = feedback.get('suggestions', []) if feedback.get('suggestions') else generate_suggestions(s, e, i, se, script_text)
            final_summary = feedback.get('summary', u'整体表现不错')
        else:
            final_speed, final_emotion, final_interaction, final_selling = s, e, i, se
            final_suggestions = generate_suggestions(s, e, i, se, script_text)
            final_summary = feedback.get('summary', '') or u'整体表现不错，有提升空间'

        ai_used = bool(ai_valid and ai_diff)
        scores = [final_speed, final_emotion, final_interaction, final_selling]
        # 直播间进阶（2026-10-05）：AI 每维度给出 evidence（引用原文的一句话依据），
        # 前端随分数展示；规则路径无 evidence 则不下发该键。
        evidence = None
        if ai_used:
            ev = {}
            for dim in ('speed', 'emotion', 'interaction', 'selling'):
                t = str(feedback.get(dim + '_evidence', '') or '').strip()[:120]
                if t:
                    ev[dim + '_score'] = t
            if ev:
                evidence = ev
        fb_body = {
            "speed_score": scores[0],
            "emotion_score": scores[1],
            "interaction_score": scores[2],
            "selling_score": scores[3],
            "overall_score": round(sum(scores) / 4),
            "summary": final_summary,
            "suggestions": final_suggestions[:3],
            # EC2：把「这个分是谁给的」明确下发，前端据此标注，不再冒充 AI 评分。
            "source": "ai" if ai_used else "rule",
            "source_note": "" if ai_used else u"本次未采用 AI 评分，分数由规则分析给出（可复现，仅反映文本特征）"
        }
        if evidence:
            fb_body["evidence"] = evidence
        return jsonify({"success": True, "feedback": fb_body})
    except Exception as e:
        # EC2/EC5：AI 失败必须可见 —— 不再无声地拿规则分冒充 AI 评分。
        logger.error(u"AI评分失败: %s", e)
        s, e, i, se = analyze_script(script_text)
        suggestions = generate_suggestions(s, e, i, se, script_text)
        return jsonify({"success": True, "feedback": {
            "speed_score": s, "emotion_score": e, "interaction_score": i, "selling_score": se,
            "overall_score": round((s + e + i + se) / 4),
            "summary": u"本次未能调用 AI，以下为规则分析结果",
            "suggestions": suggestions,
            "source": "rule",
            "source_note": u"AI 调用失败，分数由规则分析给出（可复现，仅反映文本特征）"
        }})


# ==================== 商品文案 ====================

@ecommerce_bp.route('/api/ecommerce/copywriting', methods=['POST'])
def generate_copywriting():
    """AI生成商品文案 - 支持多种格式"""
    data = request.get_json() or {}
    product = str(data.get('product', '') or '').strip() or u'荔枝'
    fmt = str(data.get('format', '') or '').strip() or u'详情页'
    audience = data.get('audience', '')
    selling_points = data.get('selling_points', '')
    tone = data.get('tone', '')

    # EC6/EC9：本接口此前既无限流也无校验，与 /script 一并对齐。
    if rate_limited('ec-copy:' + client_key(), EC_RATE_COPY_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": u"请求过于频繁，请稍后再试"}), 429
    if not ec_product_ok(product):
        return jsonify({"success": False, "code": "unknown_product",
                        "message": u"暂不支持该农产品，请从列表中选择"}), 400
    if fmt not in EC_COPY_FORMATS:
        return jsonify({"success": False, "code": "unknown_format",
                        "message": u"不支持的文案类型"}), 400

    config = EC_COPY_FORMAT_PROMPTS.get(fmt, EC_COPY_FORMAT_PROMPTS[u'详情页'])
    extra = []
    if audience:
        extra.append(u"目标人群：%s" % audience)
    if selling_points:
        extra.append(u"必须包含的卖点：%s" % selling_points)
    if tone:
        extra.append(u"语调要求：%s" % tone)
    extra_text = '\n'.join(extra) if extra else ''

    try:
        result = call_ai_service(
            system_prompt=u"""你是顶级电商文案专家，擅长为广东特色农产品撰写高转化率文案。

【文案类型】%s
【输出结构】%s
【风格要求】%s

【通用要求】
- 语言生动有画面感，避免空洞的"品质保证"类套话
- 善用场景、情感、对比等说服技巧；**具体数据一律不要自行编造**
- 突出广东/岭南地域特色和产品差异化优势
- 输出格式清晰，用markdown排版

%s""" % (config['desc'], config['structure'], config['style'], _EC_PROMO_RULE),
            user_message=u"请为「%s」撰写%s文案。\n%s" % (product, fmt, extra_text),
            model=chat_model()
        )
        return jsonify({"success": True, "copywriting": result, "format": fmt})
    except Exception as e:
        # EC5：与 /script 一致 —— 降级必须可见。
        logger.error(u"文案生成失败: %s", e)
        fallback = generate_fallback_copywriting(product, fmt)
        return jsonify({"success": True, "degraded": True,
                        "copywriting": fallback, "format": fmt})


@ecommerce_bp.route('/api/ecommerce/copy/feedback', methods=['POST'])
def copy_feedback():
    """商品文案规则评分（2026-10-05 走查 P1-2）。纯规则、可复现，无 AI 依赖。"""
    data = request.get_json() or {}
    text = str(data.get('script', '') or '')
    fmt = str(data.get('format', '') or u'详情页').strip()
    if rate_limited('ec-copy-feedback:' + client_key(), EC_RATE_FEEDBACK_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": u"请求过于频繁，请稍后再试"}), 429
    if not text.strip():
        return jsonify({"success": False, "code": "empty_script",
                        "message": u"请先写出你的文案"}), 400
    if len(text) > EC_COPY_MAX_LEN:
        return jsonify({"success": False, "code": "script_too_long",
                        "message": u"文案过长，请控制在 %d 字以内" % EC_COPY_MAX_LEN}), 400
    # 评分实现只有共享层一份（shared.copywriting.copy_score）：它评的是
    # 「结构 / 卖点 / 格式契合 / 合规」四个维度，直播与文案两条链路都不各自复制。
    return jsonify({"success": True, "feedback": copy_score(text, fmt)})


# ==================== 客服对练 ====================

@ecommerce_bp.route('/api/ecommerce/customer-service', methods=['POST'])
def simulate_customer_service():
    """AI客服模拟 - 多场景、多性格、实时评分"""
    data = request.get_json() or {}
    message = str(data.get('message', '') or '')
    history = data.get('history', [])
    scenario = data.get('scenario', u'售前咨询')
    difficulty = data.get('difficulty', u'进阶')
    personality = data.get('personality', u'友善型')
    # 本模块的产品是**自由文本**（学员可自填），不做白名单，但必须限长，避免 prompt 注入面。
    product = str(data.get('product', '') or '').strip()[:30] or u'农产品'

    # EC6：逐轮对话型接口，此前同样无限流。限额按「一轮一次调用」放宽。
    if rate_limited('ec-cs:' + client_key(), EC_RATE_CS_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": u"对话过于频繁，请稍后再试"}), 429
    if not message.strip():
        return jsonify({"success": False, "code": "empty_message",
                        "message": u"请先输入你的回复"}), 400

    sc = EC_CS_SCENARIOS.get(scenario, EC_CS_SCENARIOS[u'售前咨询'])
    pc = EC_CS_PERSONALITIES.get(personality, EC_CS_PERSONALITIES[u'友善型'])

    system_prompt = u"""【重要】你必须只扮演客户角色，绝对不能扮演客服！

你的身份：一个想买%s的网购客户。
性格：%s
场景：%s（%s）
难度：%s

【你只能说客户该说的话】
- 提出问题、表达顾虑、追问细节
- 对客服的回答表示满意或不满
- 提出新的要求或疑虑
- 绝对不能说"亲""您好""帮您处理"等客服用语

【对话节奏】
- 客服回答好 → 表示认可，可以追问或说"那行，我下单了"
- 客服回答差 → 追问、质疑、表达不满
- 客服没解决问题 → 继续追问，不要轻易放过

【回复要求】
- 不超过60字
- 口语化，像真人在聊天
- 不要输出括号里的动作描述
- 不要输出任何解释，只输出客户说的话""" % (
        product, pc, scenario, sc['desc'],
        EC_CS_DIFFICULTY_PROMPTS.get(difficulty, EC_CS_DIFFICULTY_PROMPTS[u'进阶'])
    )

    try:
        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-8:]:
            messages.append({"role": h.get('role', 'user'), "content": h.get('content', '')})
        messages.append({"role": "user", "content": message})

        # EC10：原先这里是**裸 requests.post**，绕过了统一入口 chat_completion ——
        # 既缺上游响应结构校验（空正文会被静默当成有效回复），也违反本项目
        # 「所有 AI 调用一律走 chat_completion / call_ai_service」这条红线。现改回统一入口。
        reply = chat_completion(
            messages, temperature=0.7,
            max_tokens=200 + AI_REASONING_TOKEN_RESERVE,
            timeout=30, model=chat_model()
        ).strip()

        # 分析客服表现（规则关键词评分，评的是**学员自己的回复**，对象正确）
        score = analyze_service_reply(message, reply, scenario, history, difficulty)
        sentiment = _sentiment_from_score(score['total'])

        return jsonify({"success": True, "reply": reply, "score": score, "sentiment": sentiment})
    except Exception as e:
        # EC5：降级必须可见。
        logger.error(u"客服模拟失败: %s", e)
        # 根据对话历史和客服回复动态生成fallback
        reply = generate_dynamic_fallback(scenario, product, personality, history, message)
        score = analyze_service_reply(message, reply, scenario, history, difficulty)
        sentiment = _sentiment_from_score(score['total'])
        return jsonify({"success": True, "degraded": True, "reply": reply, "score": score,
                        "sentiment": sentiment})


@ecommerce_bp.route('/api/ecommerce/customer-service/next', methods=['POST'])
def get_next_customer_msg():
    """AI生成下一句客户消息（用于主动引导对话）"""
    data = request.get_json() or {}
    scenario = data.get('scenario', u'售前咨询')
    personality = data.get('personality', u'友善型')
    product = str(data.get('product', '') or '').strip()[:30] or u'农产品'
    history = data.get('history', [])

    # EC6：补限流（本接口同样调用上游）。P3（2026-10-06）：辅助接口拆到 ec-cs-aux，
    # 避免频繁点「提示/开场白」挤占正常对话的 ec-cs 额度。
    if rate_limited('ec-cs-aux:' + client_key(), EC_RATE_CS_AUX_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": u"操作过于频繁，请稍后再试"}), 429

    sc_map = {
        u'售前咨询': u'询问%s的品质、价格、发货等信息' % product,
        u'售后处理': u'反馈收到的%s有问题，要求处理' % product,
        u'投诉应对': u'对%s或服务不满意，情绪激动' % product,
        u'议价谈判': u'想买%s但要求优惠' % product,
        u'产品推荐': u'想买%s但不确定选什么' % product
    }

    try:
        result = call_ai_service(
            system_prompt=u"""你是一个电商客户，性格：%s。
场景：%s，%s。
请生成一句自然的客户开场白或追问，不超过50字，口语化。
只输出客户说的话，不要其他内容。""" % (personality, scenario, sc_map.get(scenario, '')),
            user_message=u"请生成一句客户消息",
            model=chat_model()
        )
        return jsonify({"success": True, "message": result.strip()})
    except Exception:
        fallback = EC_CS_NEXT_FALLBACKS
        message = fallback.get(scenario, u'你好')
        return jsonify({"success": True, "degraded": True,
                        "message": message.format(product=product)
                        if '{product}' in message else message})


@ecommerce_bp.route('/api/ecommerce/customer-service/hint', methods=['POST'])
def get_service_hint():
    """根据当前对话动态生成回复建议"""
    data = request.get_json() or {}
    scenario = data.get('scenario', u'售前咨询')
    personality = data.get('personality', u'友善型')
    product = str(data.get('product', '') or '').strip()[:30] or u'农产品'
    history = data.get('history', [])
    last_customer_msg = data.get('last_customer_msg', '')

    # EC6：补限流（本接口同样调用上游）。P3（2026-10-06）：辅助接口拆到 ec-cs-aux。
    if rate_limited('ec-cs-aux:' + client_key(), EC_RATE_CS_AUX_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": u"操作过于频繁，请稍后再试"}), 429

    # 获取最近的对话上下文
    recent = history[-4:] if len(history) > 4 else history
    context = '\n'.join(
        u"%s：%s" % (u'客户' if h.get('role') == 'assistant' else u'客服', h.get('content', ''))
        for h in recent
    )

    try:
        result = call_ai_service(
            system_prompt=u"""你是客服培训专家。根据当前对话情况，给出具体的回复建议。

【场景】%s，客户性格：%s，产品：%s

【输出格式】严格JSON，不要其他文字：
{{
    "analysis": "客户当前的真实需求/情绪（15字内）",
    "strategy": "推荐的回复策略（15字内）",
    "templates": ["建议回复1（可直接复制使用）", "建议回复2", "建议回复3"],
    "tips": ["注意事项1", "注意事项2"]
}}

【要求】
- 建议回复要口语化、自然、不超过50字
- 根据客户性格调整语气（急躁的要快速回应，犹豫的要给信心）
- 根据对话阶段调整策略（初期多了解需求，中期解决问题，后期促单）""" % (
                scenario, personality, product),
            user_message=u"最近对话：\n%s\n\n客户最新消息：%s\n\n请给出回复建议。" % (
                context, last_customer_msg),
            model=chat_model()
        )
        json_match = re.search(r'\{.*?\}', result, re.DOTALL)
        hint = json.loads(json_match.group()) if json_match else {}
        return jsonify({"success": True, "hint": hint})
    except Exception:
        # 根据对话上下文动态生成建议
        hint = generate_dynamic_hint(scenario, product, personality, last_customer_msg, history)
        return jsonify({"success": True, "degraded": True, "hint": hint})


__all__ = [
    'ecommerce_bp',
    'EC_PRODUCTS', 'EC_STYLE_KEYS', 'EC_COPY_FORMATS', '_EC_PROMO_RULE',
    'generate_fallback_copywriting',
    'generate_dynamic_fallback', 'generate_dynamic_hint',
    'analyze_service_reply', '_sentiment_from_score',
    'copy_score',
]
