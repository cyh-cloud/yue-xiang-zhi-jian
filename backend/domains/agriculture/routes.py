# -*- coding: utf-8 -*-
"""农业培训域路由：农技问答（含流式）与追问建议。

从 app.py 迁出（后端按领域拆分 T10），URL、请求响应结构、状态码、错误码保持不变。
农事日历、农产品目录、作物订阅与到期提醒在 calendar.py，静态兜底建议与两个纯函数
在 calendar_data，本文件只留问答这一条链路。

本域的边界（见 docs/adr/0001-backend-domain-split.md）：

- 农技问答的系统提示词与作物名解析在 domains.agriculture.prompts（T03 下沉），
  本模块直接取用，不复制第二份。
- 农技口径的**判定函数** has_chem_dosage 在共享层 shared.agri_dosage：病虫害诊断域
  与方言问答域也判定它，所以判定只能有一处；命中后要展示的免责声明文案
  CHEM_DOSE_NOTICE_BLOCK 在本域（prompts），由本域自己决定怎么说。
- 上游模型调用一律走共享层 ai.client（chat_completion / stream_chat_completion /
  call_ai_service / chat_model），「上游是否已配置」按模块属性调用
  ai.client.ai_configured()：测试模拟「上游未配置」时改写的是这个模块属性，
  也就是开关的真正持有者，import 时绑定本地名字会让 patch 失效。
- 会话取用户与限流走共享层 core.session，本域不再持有第二份会话实现。

未随本域迁走的两个 helper：chat_completion 是 app.py 里 ai.client.chat_completion 的
一份逐字重复（被三个领域使用，属共享层既有实现，本次只把本域的这一处调用改指共享层）；
_chem_dose_notice_for 只服务本土资源域的方言问答，随那个域走。
"""

import json
import logging
import os
import time

from flask import Blueprint, jsonify, request, Response, stream_with_context

import ai.client

from ai.client import (
    AI_REASONING_TOKEN_RESERVE,
    call_ai_service,
    chat_completion,
    chat_model,
    stream_chat_completion,
)
from core.session import client_key, rate_limited
from domains.agriculture.prompts import (
    CHEM_DOSE_NOTICE_BLOCK,
    agri_system_prompt,
    agriculture_product_name,
    supported_products,
)
from shared.agri_dosage import has_chem_dosage

logger = logging.getLogger(__name__)

agriculture_bp = Blueprint('agriculture', __name__)


# ---- 农业问答：输入约束与限流 ----
AGRI_QUESTION_MAX_LEN = 500          # 单条问题最大字符数（与前端 maxlength 保持一致）
AGRI_HISTORY_MAX_TURNS = 5           # 参与上下文的历史轮数上限
AGRI_HISTORY_MAX_CHARS = 4000        # 参与上下文的历史总字符上限
AGRI_RATE_WINDOW = 300               # 限流窗口（秒）
AGRI_RATE_ASK_LIMIT = int(os.getenv('AGRI_RATE_ASK_LIMIT', '60'))          # 每窗口内问答请求上限
AGRI_RATE_SUGGEST_LIMIT = int(os.getenv('AGRI_RATE_SUGGEST_LIMIT', '120'))  # 每窗口内建议请求上限

# 问答接口接受的作物集合：缺陷 A5 的未知作物拒绝表（prompts 里的内置兜底名表）。
_AGRI_SUPPORTED_PRODUCTS = supported_products()

# 下发前端的文案不暴露部署细节（匿名访客同样能看到这条消息）；
# 具体排查指引只写进服务端日志。
AI_NOT_CONFIGURED_MSG = (
    'AI 农技问答尚未启用，请联系平台管理员。'
    '如需即时帮助，可咨询当地农技站或拨打 12316 三农服务热线。'
)
AI_NOT_CONFIGURED_LOG = 'AI_API_KEY 未配置：请在项目根目录 .env 中填入有效密钥后重启服务'
AI_UNAVAILABLE_MSG = (
    'AI 服务暂时不可用，请稍后重试。'
    '如需即时帮助，可咨询当地农技站或拨打 12316 三农服务热线。'
)

# 建议问题缓存
_suggestions_cache = {}
_suggestions_cache_time = {}
SUGGESTIONS_CACHE_TTL = 300  # 5分钟


def _parse_agri_request():
    """解析并校验问答请求。返回 (payload, error_response)，error_response 非空即需直接返回。"""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({
            "success": False, "code": "bad_request",
            "message": "请求格式不正确，应为 JSON 对象"
        }), 400)

    question = str(data.get('question', '') or '').strip()
    if not question:
        return None, (jsonify({
            "success": False, "code": "empty_question",
            "message": "请输入问题"
        }), 400)
    if len(question) > AGRI_QUESTION_MAX_LEN:
        return None, (jsonify({
            "success": False, "code": "question_too_long",
            "message": f"问题过长，请控制在 {AGRI_QUESTION_MAX_LEN} 字以内"
        }), 400)

    history = data.get('history', [])
    if not isinstance(history, list):
        history = []

    # A5：未知 product 明确拒绝，不再退化成一个跟作物无关的泛泛回答。
    # 缺省（未传/空串）与诊断接口保持一致的宽容度：按荔枝处理，避免生成无作物针对性的提示词。
    product = str(data.get('product', '') or '').strip() or 'lychee'
    if product not in _AGRI_SUPPORTED_PRODUCTS:
        return None, (jsonify({
            "success": False, "code": "unknown_product",
            "message": "暂不支持该农产品，请从列表中选择"
        }), 400)

    return {
        "question": question,
        "product": product,
        "history": history,
    }, None


def _build_agri_messages(system_prompt, history, question):
    """按「轮数 + 字符数」双重上限拼装上下文，避免历史本身撑爆上下文窗口。"""
    messages = [{"role": "system", "content": system_prompt}]
    picked = []
    used = 0
    for item in reversed(history[-AGRI_HISTORY_MAX_TURNS:]):
        if not isinstance(item, dict):
            continue
        q = str(item.get('question', '') or '').strip()
        a = str(item.get('answer', '') or '').strip()
        if not q or not a:
            continue
        cost = len(q) + len(a)
        if used + cost > AGRI_HISTORY_MAX_CHARS:
            break
        used += cost
        picked.append((q, a))
    for q, a in reversed(picked):
        messages.append({"role": "user", "content": q})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": question})
    return messages


def _generate_suggestions(product, question, answer):
    """基于当前问答生成3个追问建议。任何失败都返回空列表，不抛异常、不影响主回答。"""
    product_name = agriculture_product_name(product)
    try:
        result = call_ai_service(
            system_prompt=f"你是{product_name}种植专家。根据用户的问题和AI回答，生成3个相关的追问建议。只输出3个问题，每行一个，不要编号，不要其他内容。每个问题控制在20字以内。",
            user_message="用户问：%s\nAI答：%s" % (str(question or '')[:200], str(answer or '')[:200]),
            max_tokens=300 + AI_REASONING_TOKEN_RESERVE,
            temperature=0.6,
            model=chat_model()
        )
    except Exception as e:
        logger.warning("生成追问建议失败: %s", e)
        return []

    items = []
    for raw in str(result or '').split('\n'):
        text = raw.strip().lstrip('0123456789.、）) ').strip()
        if text and len(text) <= 40:
            items.append(text)
    return items[:3]


@agriculture_bp.route('/api/agriculture/ask', methods=['POST'])
def ask_agriculture():
    payload, err = _parse_agri_request()
    if err:
        return err

    if rate_limited('ask:' + client_key(), AGRI_RATE_ASK_LIMIT):
        return jsonify({
            "success": False, "code": "rate_limited",
            "message": "提问过于频繁，请稍后再试"
        }), 429

    question = payload['question']
    product = payload['product']
    messages = _build_agri_messages(agri_system_prompt(product), payload['history'], question)

    # 未配置密钥：明确告知，不再返回一条伪装成正常回答的兜底文案
    if not ai.client.ai_configured():
        logger.warning("AI问答被调用但未配置密钥：%s", AI_NOT_CONFIGURED_LOG)
        return jsonify({
            "success": False, "code": "ai_not_configured",
            "message": AI_NOT_CONFIGURED_MSG
        }), 503

    try:
        # max_tokens 必须带上推理余量：推理模型（step-3.7-flash）会先花额度思考，
        # 实测一次问答就思考 1200-1600 字，800 的额度会被吃光，正文直接是空串。
        # 与流式路径（stream_chat_completion 内部已加）保持同一预算口径。
        answer = chat_completion(messages, temperature=0.4,
                                  max_tokens=800 + AI_REASONING_TOKEN_RESERVE,
                                  timeout=30, model=chat_model())
    except Exception as e:
        logger.error("AI问答失败: %s", e)
        return jsonify({
            "success": False, "code": "ai_unavailable",
            "message": AI_UNAVAILABLE_MSG
        }), 503

    # A2：正文里出现用量 / 稀释倍数 / 安全间隔期时，服务端强制补免责声明。
    # 放在生成追问建议之前，让建议基于补齐后的完整回答。
    if has_chem_dosage(answer):
        answer = answer.rstrip() + CHEM_DOSE_NOTICE_BLOCK

    # 追问建议失败不影响主回答
    try:
        suggestions = _generate_suggestions(product, question, answer)
    except Exception as e:
        logger.warning("生成追问建议失败: %s", e)
        suggestions = []

    return jsonify({"success": True, "answer": answer, "suggestions": suggestions})


@agriculture_bp.route('/api/agriculture/ask/stream', methods=['POST'])
def ask_agriculture_stream():
    """SSE 流式 AI 问答"""
    payload, err = _parse_agri_request()
    if err:
        return err

    if rate_limited('ask:' + client_key(), AGRI_RATE_ASK_LIMIT):
        return jsonify({
            "success": False, "code": "rate_limited",
            "message": "提问过于频繁，请稍后再试"
        }), 429

    if not ai.client.ai_configured():
        logger.warning("SSE问答被调用但未配置密钥：%s", AI_NOT_CONFIGURED_LOG)
        return jsonify({
            "success": False, "code": "ai_not_configured",
            "message": AI_NOT_CONFIGURED_MSG
        }), 503

    question = payload['question']
    product = payload['product']
    messages = _build_agri_messages(agri_system_prompt(product), payload['history'], question)
    collected = []

    def generate():
        try:
            # 流式调用走共享层唯一出口（模型选择、思考余量、SSE 分片解析都在那里）
            for content in stream_chat_completion(messages, temperature=0.4, max_tokens=800):
                collected.append(content)
                yield f'data: {json.dumps({"content": content}, ensure_ascii=False)}\n\n'

            # 上游「成功但没内容」也是一种失败，必须让前端知道，不能留一个空气泡
            if not ''.join(collected).strip():
                raise ValueError('上游未返回任何内容')

            # A2：正文出现用药数值时强制补免责声明。必须在 event: done 之前发出 ——
            # 前端收到 done 就会收尾气泡并渲染操作按钮，之后再发的内容不会被渲染。
            if has_chem_dosage(''.join(collected)):
                yield 'data: %s\n\n' % json.dumps(
                    {"content": CHEM_DOSE_NOTICE_BLOCK}, ensure_ascii=False)
        except Exception as e:
            logger.error("SSE问答失败: %s", e)
            yield 'event: error\ndata: %s\n\n' % json.dumps(
                {"code": "ai_unavailable", "message": AI_UNAVAILABLE_MSG},
                ensure_ascii=False)
            return

        # 先收尾正文（前端据此渲染操作按钮），再补发追问建议，
        # 避免「建议生成」这段额外耗时拖慢回答的收尾。
        yield 'event: done\ndata: [DONE]\n\n'

        try:
            suggestions = _generate_suggestions(product, question, ''.join(collected))
        except Exception as e:
            logger.warning("流式追问建议生成失败: %s", e)
            suggestions = []
        if suggestions:
            yield 'event: suggestions\ndata: %s\n\n' % json.dumps(
                {"suggestions": suggestions}, ensure_ascii=False)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@agriculture_bp.route('/api/agriculture/suggestions', methods=['GET'])
def get_agriculture_suggestions():
    """获取指定农产品的常见问题建议。

    建议栏属于「锦上添花」的辅助内容：任何失败都返回空列表，
    对前端始终返回 success=True，不把错误抛给用户。

    AI 不可用时明确不给建议（空列表），不再退到一份静态问题清单
    （REFACTOR-PLAN 4.2）：那六条问题是写死在代码里的内容，既覆盖不到全部
    8 个作物，也会让人误以为平台在回答。前端拿不到建议时按当前作物渲染
    通用问句（script.js 的 QA_GENERIC_QUESTIONS），这才是「不可用」的如实呈现。
    """
    product = request.args.get('product', 'lychee')
    now = time.time()

    # 命中缓存不消耗配额
    if product in _suggestions_cache and now - _suggestions_cache_time.get(product, 0) < SUGGESTIONS_CACHE_TTL:
        return jsonify({"success": True, "suggestions": _suggestions_cache[product]})

    if rate_limited('suggest:' + client_key(), AGRI_RATE_SUGGEST_LIMIT):
        return jsonify({"success": True, "suggestions": []})

    if not ai.client.ai_configured():
        return jsonify({"success": True, "suggestions": []})

    product_name = agriculture_product_name(product)
    try:
        result = call_ai_service(
            system_prompt=f"你是{product_name}种植专家。生成4个农民最常问的实用问题，每行一个，不要编号，不要其他内容。每个问题控制在15-25字。要覆盖不同方面（种植、病虫害、施肥、采收等）。",
            user_message=f"请为{product_name}生成4个常见问题",
            max_tokens=300 + AI_REASONING_TOKEN_RESERVE,
            temperature=0.7,
            model=chat_model()
        )
        suggestions = [s.strip().lstrip('0123456789.、 ') for s in result.strip().split('\n') if s.strip()][:4]
        if not suggestions:
            raise ValueError('上游未返回可用问题')
        _suggestions_cache[product] = suggestions
        _suggestions_cache_time[product] = now
        return jsonify({"success": True, "suggestions": suggestions})
    except Exception as e:
        logger.error("生成建议问题失败: %s", e)
        return jsonify({"success": True, "suggestions": []})


__all__ = ['agriculture_bp', 'SUGGESTIONS_CACHE_TTL']
