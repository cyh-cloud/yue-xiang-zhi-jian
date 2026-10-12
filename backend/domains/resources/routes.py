# -*- coding: utf-8 -*-
"""本土资源域路由：方言问答、成功案例、政策信息。

从 app.py 迁出（后端按领域拆分 T14），URL、请求响应结构、状态码、错误码保持不变。

本域的边界（见 docs/adr/0001-backend-domain-split.md）：

- 方言知识库与方言话术库（上游不可用时的降级文案）在 dialect_voice.py，本域自己的资产；
- 案例与政策的**内容**在 domain_data.resources（cases_data / policies_data），
  读取与口径说明经 database 契约层取，本域不持有第二份内容；
- 农技口径（用药数值判定 + 免责声明）在共享层 shared.agri_dosage，与农业培训域、
  病虫害诊断域共用同一份，只在本域按 chem_notice 单独字段下发；
- 上游调用走共享层 ai.client，限流与限流键走共享层 core.session。

⚠️ 政策有一条不能碰的红线，见 get_policies 的注释。
"""

import json
import logging
import os

from flask import Blueprint, jsonify, request

from ai.client import (
    AI_REASONING_TOKEN_RESERVE,
    call_ai_service,
    chat_completion,
    chat_model,
)
from core.session import client_key, rate_limited
import database

from domains.resources.dialect_voice import (
    _chem_dose_notice_for,
    DIALECTS_DATA,
    dialect_fallback_answer,
)

resources_bp = Blueprint('resources', __name__)


logger = logging.getLogger(__name__)


# 方言语音问答的限流额度（缺陷 A7）：该接口同样走 chat_model()，在 AI_API_KEY 生效
# 之前只是个隐患，现在是**可被白刷算力的入口**。口径与农技问答对齐（同一个窗口、
# 同为对话型调用），可用环境变量覆盖。窗口长度由 core.session 全站统一给出。
VOICE_RATE_LIMIT = int(os.getenv('VOICE_RATE_LIMIT', '60'))   # 每窗口内语音问答请求上限


@resources_bp.route('/api/resources/dialects', methods=['GET'])
def get_dialects():
    dialects = [{"id": v["id"], "name": v["name"], "region": v["region"],
                 "emoji": v["emoji"], "areas": v["areas"], "speakers": v["speakers"]}
                for v in DIALECTS_DATA.values()]
    return jsonify({"success": True, "dialects": dialects})


@resources_bp.route('/api/resources/dialect-info', methods=['GET'])
def get_dialect_info():
    """获取方言详细信息（问候、短语、快捷问题）"""
    dialect_id = request.args.get('dialect', 'cantonese')
    d = DIALECTS_DATA.get(dialect_id, DIALECTS_DATA['cantonese'])
    return jsonify({"success": True, "info": {
        "id": d["id"], "name": d["name"], "region": d["region"],
        "emoji": d["emoji"], "areas": d["areas"], "speakers": d["speakers"],
        "greeting": d["greeting"], "greeting_meaning": d["greeting_meaning"],
        "features": d["features"], "phrases": d["phrases"],
        "quick_questions": d["quick_questions"]
    }})


@resources_bp.route('/api/resources/cases', methods=['GET'])
def get_success_cases():
# 内容唯一事实源 = domain_data.resources.cases_data（经 database.get_success_cases 读取，不落库）
    # ⚠️ 只下发**超级管理员审核通过**的案例（审核状态存 content_reviews，见 _seed_case_reviews）
    cases = database.get_success_cases()
    payload = {"success": True, "cases": cases}
    payload.update(database.get_case_notes())
    # 附审核统计：前端据此区分"审核中"与"加载失败"，不把待审当成没数据
    payload.update(database.get_case_review_stats())
    return jsonify(payload)


@resources_bp.route('/api/resources/cases/<int:case_id>', methods=['GET'])
def get_success_case(case_id):
    # 同样只认审核通过的案例 —— 否则未通过/已驳回的案例能靠直链看到，审核就形同虚设
    cases = database.get_success_cases()
    case = next((c for c in cases if c['id'] == case_id), None)
    if case:
        return jsonify({"success": True, "case": case})
    return jsonify({"success": False, "message": "案例不存在或尚未通过审核"}), 404


@resources_bp.route('/api/resources/policies', methods=['GET'])
def get_policies():
    # 学员端唯一的政策来源 = 政府端政策表（government_policies）中 is_published=1 的行。
    #
    # ⚠️ 这里**绝不能**再降级到旧 `policies` 表（原实现 `gp if gp else database.get_policies()`）：
    #    平台预置的 5 条政策在两张表里各存了一份，政府端把政策**全部下架**时
    #    `get_government_policies()` 返回空 → 降级逻辑把旧表那 5 条端上学員端
    #    → 政务人员明明点了「下架」，学员端却一条没少（实测表现为"下架完全无效"）。
    #    下架是政府对外的正式动作，必须真实生效；学员端「空」就是要如实呈现为空。
    policies = database.get_government_policies()
    payload = {"success": True, "policies": policies}
# 口径说明（来源说明 + 免责声明）与内容同源，由 domain_data.resources.policies_data 提供
    payload.update(database.get_policy_notes())
    return jsonify(payload)


@resources_bp.route('/api/resources/voice', methods=['POST'])
def process_voice():
    """处理语音/文字输入 — 支持对话历史"""
    data = request.get_json()
    text = data.get('text', '')
    dialect = data.get('dialect', 'cantonese')
    history = data.get('history', [])  # 最近对话历史

    if not text:
        return jsonify({"success": False, "message": "未收到内容"})

    # A7：本接口此前**没有任何限流**，而它同样走 chat_model() 调用上游。
    # 限流键与其它 AI 路由共用 client_key()，错误体结构与农技问答保持一致。
    if rate_limited('voice:' + client_key(), VOICE_RATE_LIMIT):
        return jsonify({
            "success": False, "code": "rate_limited",
            "message": "提问过于频繁，请稍后再试"
        }), 429

    d = DIALECTS_DATA.get(dialect, DIALECTS_DATA['cantonese'])
    dialect_name = d['name']
    areas = d['areas']

    # 构建对话历史
    messages = [{
        "role": "system",
        "content": f"""你是粤乡智匠平台的AI农业助手，精通{dialect_name}（{areas}地区）。
用户用{dialect_name}方言提问，你也必须用{dialect_name}方言回答！
要求：
1. 全程用{dialect_name}方言回答，不要用普通话
2. 语气亲切自然，像老乡之间聊天
3. 回答简洁实用，200字以内
4. 涉及病虫害给出具体防治方案
5. 结合广东本地气候和种植习惯
6. 如果不确定某个方言词怎么写，就用普通话混搭，但整体风格必须是{dialect_name}"""
    }]
    # 加入历史对话（最多5轮）
    for h in history[-5:]:
        if h.get('user'):
            messages.append({"role": "user", "content": h['user']})
        if h.get('bot'):
            messages.append({"role": "assistant", "content": h['bot']})
    messages.append({"role": "user", "content": text})

    try:
        # 走统一入口：自带推理模型的思考余量、上游结构校验，以及「被 max_tokens 截断」的识别。
        # 上游失败时由外层 except 退到本地方言话术库，降级行为与改动前一致。
        answer = chat_completion(
            messages,
            temperature=0.4,
            max_tokens=600 + AI_REASONING_TOKEN_RESERVE,
            timeout=60,
            model=chat_model()
        )

        # 生成追问建议
        suggestions = []
        try:
            sug_resp = call_ai_service(
                system_prompt="根据用户的问题和你的回答，生成3个相关的追问建议。返回JSON数组格式，如：[\"问题1\",\"问题2\",\"问题3\"]。只返回JSON。",
                user_message=f"用户问题：{text}\n回答：{answer}",
                temperature=0.5, max_tokens=300 + AI_REASONING_TOKEN_RESERVE,
                model=chat_model()
            )
            clean = sug_resp.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            suggestions = json.loads(clean)[:3]
        except:
            # 根据用户问题生成动态追问建议
            sug_map = {
                u"施肥": [u"有机肥和化肥怎么搭配？", u"叶面肥什么时候喷？", u"施肥后要浇水吗？"],
                u"病": [u"怎么区分真菌和细菌病害？", u"打药要注意什么？", u"有没有不用药的方法？"],
                u"虫": [u"黄板蓝板怎么选？", u"什么虫害最常见？", u"天敌怎么保护？"],
                u"种植": [u"第一年怎么管理？", u"什么时候种最好？", u"要挖多大的坑？"],
                u"修剪": [u"什么时候修剪最好？", u"大枝小枝怎么分？", u"修剪后怎么护理？"],
                u"直播": [u"开场怎么吸引人？", u"产品怎么展示？", u"怎么引导下单？"],
                u"电商": [u"图片怎么拍好看？", u"标题怎么写？", u"怎么处理售后？"]
            }
            suggestions = None
            for kw, sugs in sug_map.items():
                if kw in text:
                    suggestions = sugs
                    break
            if not suggestions:
                suggestions = [f"{text}有什么技巧？", "需要注意什么问题？", "有没有成功案例？"]

        return jsonify({"success": True, "result": {
            "text": text, "dialect": dialect, "dialect_name": dialect_name,
            "answer": answer, "suggestions": suggestions,
            "source": "ai",
            # 用药口径：与农技问答 / 诊断同一条红线 —— 给了用量就必须给用户提示
            "chem_notice": _chem_dose_notice_for(answer)
        }})
    except Exception as e:
        logger.error(f"语音处理失败: {e}")
        answer, suggestions = dialect_fallback_answer(text, dialect)
        return jsonify({"success": True, "result": {
            "text": text, "dialect": dialect, "dialect_name": dialect_name,
            "answer": answer, "suggestions": suggestions,
            "source": "fallback",
            # 降级话术库里就写着具体用量与施用间隔，同样必须提示
            "chem_notice": _chem_dose_notice_for(answer)
        }})


__all__ = ['resources_bp']
