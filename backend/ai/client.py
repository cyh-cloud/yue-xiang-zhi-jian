# -*- coding: utf-8 -*-
"""上游模型调用：配置、同步补全、流式补全、多模态补全。

全站所有 AI 调用只有这一个出口。「是否已配置」「问答用哪个模型」这类判断也在这里，
因为它们只与上游有关，与任何业务领域无关。
"""

import json
import os

# 上游服务配置（环境变量是唯一配置入口，.env 见仓库根）
AI_API_URL = os.getenv('AI_API_URL', 'https://api.siliconflow.cn/v1/chat/completions')
AI_API_KEY = os.getenv('AI_API_KEY', '')
AI_MODEL = os.getenv('AI_MODEL', 'Qwen/Qwen3-32B')
# 视觉模型独立配置：AI_MODEL 是纯文本模型，本身不能看图。
# 单独用 AI_VL_MODEL，避免把问答/追问建议这类纯文本调用一并升级到视觉档（单次成本更高）。
# 需要关闭图片诊断时，把 AI_VL_MODEL 显式留空即可。
AI_VL_MODEL = os.getenv('AI_VL_MODEL', 'Qwen/Qwen3-VL-32B-Instruct')
# 问答/追问建议专用模型。与诊断模型分开配置，原因是两者能力面不同：
#   ① 流式体验：stepaudio-2.5-chat 实测首字 0.39~0.41s、全文 1.3s 出完；
#      step-3.7-flash 是推理模型，要先思考约 3.2s 才吐第一个正文字（总 3.6s）。
#   ② 它**只支持文本与音频**：传图片会 400「only support text and audio」，
#      且输出的诊断 JSON 键名会带空格（`{ " disease": ... }`），
#      会被诊断解析判成「缺少病害名称」。
#   所以它只能承担问答/建议，**图片诊断（AI_VL_MODEL）与结构化诊断（AI_MODEL）
#   必须留在 step-3.7-flash**。想让问答回到同一个推理模型，把这里留空即可（空值 = 跟随 AI_MODEL）。
AI_CHAT_MODEL = os.getenv('AI_CHAT_MODEL', '').strip()
# 推理强度（推理模型专用，如 step-3.7-flash 支持 low/medium/high）。
# ⚠️ 推理模型的「思考」会占用 max_tokens 额度：实测不给这个参数时，一次
# 「按 JSON 返回诊断」的请求会思考 1400+ 字、把 1000 的额度吃光，正文一个字都吐不出来。
# 实测 7 种关闭思考的写法（enable_thinking / thinking.type=disabled / reasoning_effort=none|minimal /
# enable_reason / chat_template_kwargs）全部无效，所以只能：① 调低到 low（实测思考量减少约 35%）
# ② 把各处 max_tokens 留出思考余量。非推理模型会忽略这个参数。
AI_REASONING_EFFORT = os.getenv('AI_REASONING_EFFORT', '').strip()
# 推理模型的思考余量（token）。给每个 max_tokens 预算加这么多，保证「思考完还有正文」。
AI_REASONING_TOKEN_RESERVE = int(os.getenv('AI_REASONING_TOKEN_RESERVE', '600'))


def ai_configured():
    """是否已配置可用的 AI 密钥。空密钥时上游必然返回 401，提前短路可避免无谓等待。"""
    return bool((AI_API_KEY or '').strip())


def ai_vision_configured():
    """是否具备图片诊断能力：既要有密钥，也要配置了支持图片输入的模型。"""
    return ai_configured() and bool((AI_VL_MODEL or '').strip())


def chat_model():
    """问答 / 追问建议 / 方言语音问答使用的模型。

    未单独配置 AI_CHAT_MODEL 时跟随默认文本模型 AI_MODEL，行为与只有
    AI_MODEL/AI_VL_MODEL 两个配置时完全一致。诊断路径不走这里（见 AI_CHAT_MODEL 注释）。
    """
    return (AI_CHAT_MODEL or AI_MODEL)


def chat_completion(messages, temperature=0.3, max_tokens=800, timeout=30, model=None):
    """单次调用上游 Chat Completions，返回正文文本；任何异常/结构异常均抛出。

    model 为空时使用默认文本模型 AI_MODEL；多模态调用传入 AI_VL_MODEL。
    """
    import requests
    payload = {
        "model": (model or AI_MODEL),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    # 推理模型专用；非推理模型会忽略。留空则用上游默认（思考量更大、更慢）。
    if AI_REASONING_EFFORT:
        payload["reasoning_effort"] = AI_REASONING_EFFORT
    resp = requests.post(
        AI_API_URL,
        headers={
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=timeout
    )
    resp.raise_for_status()
    data = resp.json()
    choices = data.get('choices') if isinstance(data, dict) else None
    if not choices:
        raise ValueError('上游响应缺少 choices 字段')
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get('message') if isinstance(choice.get('message'), dict) else {}
    content = message.get('content')
    if not content or not str(content).strip():
        # 推理模型（如 step-3.7-flash）会把 max_tokens 额度先花在思考上，额度不够时正文为空。
        # 必须把「额度不够」与「上游真挂了」区分开，否则只会看到一句笼统的「服务不可用」。
        reason = str(message.get('reasoning_content') or message.get('reasoning') or '')
        if choice.get('finish_reason') == 'length' or reason:
            raise ValueError(
                '上游输出被 max_tokens 截断：思考已消耗约 %d 字，正文为空（请调大 max_tokens）' % len(reason))
        raise ValueError('上游响应内容为空')
    return str(content).strip()


def stream_chat_completion(messages, temperature=0.4, max_tokens=800, timeout=(10, 60)):
    """流式调用上游 Chat Completions，产出 SSE 里已经切好的正文分片。

    调用方负责把分片拼给前端；解析（data: 前缀 / [DONE] / delta.content）与连接管理
    都收敛在这里，各领域不再自己写裸 requests.post。
    """
    import requests
    payload = {
        "model": chat_model(),
        "messages": messages,
        "temperature": temperature,
        # 推理模型会把额度先花在思考上（实测约 400 token），留出余量给正文；
        # 非推理模型（stepaudio-2.5-chat）不会思考，这只是个用不到的上限，无副作用。
        "max_tokens": max_tokens + AI_REASONING_TOKEN_RESERVE,
        "stream": True
    }
    if AI_REASONING_EFFORT:
        payload["reasoning_effort"] = AI_REASONING_EFFORT
    resp = requests.post(
        AI_API_URL,
        headers={
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        stream=True,
        timeout=timeout
    )
    resp.raise_for_status()
    try:
        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode('utf-8', 'replace')
            if not line.startswith('data: '):
                continue
            data_str = line[6:].strip()
            if data_str == '[DONE]':
                break
            try:
                chunk = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            choices = chunk.get('choices') if isinstance(chunk, dict) else None
            if not choices:
                continue
            content = (choices[0].get('delta') or {}).get('content') or ''
            if content:
                yield content
    finally:
        resp.close()


def call_ai_service(system_prompt, user_message, temperature=0.3,
                    max_tokens=1000 + AI_REASONING_TOKEN_RESERVE, model=None):
    """通用 AI 调用入口（供全站各 AI 功能复用）。

    统一走 chat_completion，因此同样受益于：
      ① 上游响应结构校验（缺 choices / 空内容会抛错，不再静默返回 None）
      ② 未配置密钥时的快速失败
      ③ 推理模型的思考余量（默认值已加上 AI_REASONING_TOKEN_RESERVE）

    model 留空时用默认文本模型 AI_MODEL；问答/建议这类对话型调用传 chat_model()。
    """
    if not ai_configured():
        raise RuntimeError('未配置 AI_API_KEY，AI 功能不可用')
    return chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=30,
        model=model
    )


def call_ai_vision_service(system_prompt, user_message, images,
                           temperature=0.3, max_tokens=2000 + AI_REASONING_TOKEN_RESERVE,
                           timeout=120):
    """多模态调用：把图片和文本一起送进支持图片输入的模型。

    与 call_ai_service 分开实现，避免改动既有签名影响纯文本功能（问答 / 追问建议）。
    images 形如 [{'mime': 'image/jpeg', 'data': '<base64>'}]，按 OpenAI 兼容的
    image_url(data URL) 结构拼进 user content 数组。
    """
    if not ai_configured():
        raise RuntimeError('未配置 AI_API_KEY，AI 功能不可用')
    model = (AI_VL_MODEL or '').strip()
    if not model:
        raise RuntimeError('未配置 AI_VL_MODEL，图片诊断不可用')

    content = [
        {"type": "image_url", "image_url": {"url": f"data:{item['mime']};base64,{item['data']}"}}
        for item in (images or [])
    ]
    content.append({"type": "text", "text": user_message})

    return chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        model=model
    )


__all__ = [
    'AI_API_URL', 'AI_API_KEY', 'AI_MODEL', 'AI_VL_MODEL', 'AI_CHAT_MODEL',
    'AI_REASONING_EFFORT', 'AI_REASONING_TOKEN_RESERVE',
    'ai_configured', 'ai_vision_configured', 'chat_model',
    'chat_completion', 'stream_chat_completion',
    'call_ai_service', 'call_ai_vision_service',
]
