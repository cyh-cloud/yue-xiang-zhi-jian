# -*- coding: utf-8 -*-
"""就业能力档案域路由装配：能力档案、简历读写、AI 简历辅助、求职意向增删查。

从 app.py 迁出（后端按领域拆分 T15），URL、请求响应结构、状态码、错误码保持不变。

链路设计（2026-10-06 用户拍板「把这些功能弄成一条链路」）：
  能力档案 → AI 简历 → 岗位匹配 → 投递/报名 → 反馈回流

两条投递通道的区别（务必保持）：
  · 企业岗位（job_listings）—— 站内投递，走 job_applications，企业端「简历管理」可见并给反馈；
  · 公开招聘公告（db_domains.recruitments，T09 起读库）—— **平台不是官方报名系统**，
    只做「求职意向登记」（job_intents），报名由学员按公告原文自行完成，
    接口文案与前端都必须显式声明这一点。

求职资料属个人数据：三条读路由与三条写路由都先过 `_self_only`，
未登录 401、他人 403。这个越权边界是本次搬迁的红线，不能有任何松动。
"""

import logging

from flask import Blueprint, jsonify, request

from ai.client import AI_REASONING_TOKEN_RESERVE, call_ai_service
import ai.client
from core.session import client_key, rate_limited, self_only_guard
from domains.employment_profile.prompts import (
    RESUME_AI_RATE_LIMIT,
    RESUME_AI_SECTION_MAX_LEN,
    RESUME_AI_SECTIONS,
    RESUME_AI_SYSTEM_PROMPT,
)
from domains.employment_profile.service import profile_for_ai
from domains.employment_profile.service import user_has_resume
from db_domains import employment
from db_domains import recruitments as recruitments_db

employment_profile_bp = Blueprint('employment_profile', __name__)

logger = logging.getLogger(__name__)


def _self_only(user_id):
    """校验「当前登录用户就是 user_id 本人」——求职资料属个人数据，不可跨用户读写。

    返回 (user, None) 或 (None, (response, status))。

    实现走共享层 core.session.self_only_guard：它与 messages_self_guard 同为
    「只能以本人身份读写」的身份护栏，按 spec 的边界件归属进共享层，消息域与
    求职资料两个领域共用一份实现，不再各写一份。
    """
    return self_only_guard(user_id, '无权访问他人的求职资料')


@employment_profile_bp.route('/api/employment/profile/<user_id>', methods=['GET'])
def get_employment_profile(user_id):
    """能力档案：聚合学员**真实**的证书 / 学习进度 / 实训成绩 / 积分。

    这些数据同时是 AI 简历的素材来源 —— 前端要把它与简历面板并排展示，
    让学员清楚「AI 是根据这些东西写的」。
    """
    user, err = _self_only(user_id)
    if err:
        return err
    profile = employment.get_learner_profile(user_id)
    return jsonify({"success": True, "profile": profile})


@employment_profile_bp.route('/api/employment/resume/<user_id>', methods=['GET'])
def get_resume(user_id):
    user, err = _self_only(user_id)
    if err:
        return err
    return jsonify({"success": True, "resume": employment.get_resume(user_id)})


@employment_profile_bp.route('/api/employment/resume/<user_id>', methods=['PUT'])
def save_resume(user_id):
    """保存在线简历（学员自填内容）。AI 产出同样走这里落库，由学员确认后再保存。"""
    user, err = _self_only(user_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    resume = employment.save_resume(user_id, data)
    return jsonify({"success": True, "message": "简历已保存", "resume": resume})


@employment_profile_bp.route('/api/employment/resume/ai', methods=['POST'])
def resume_ai_generate():
    """AI 简历辅助：**仅根据学员真实数据**起草/润色指定段落。

    红线（与全项目口径一致）：
      · AI 只做「组织与表达」，**不做事实生成**；未提供的信息一律用【待补充】占位；
      · 失败必须可见 —— 返回 503 + 明确 code，绝不返回 success=True 的兜底文案；
      · 调用成功后会置 `resumes.ai_used = 1`，前端据此如实标注「本段经 AI 辅助生成」。
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    section = (data.get('section') or '').strip()
    draft = data.get('draft') or ''

    if not user_id:
        return jsonify({"success": False, "code": "bad_request", "message": "参数不完整"}), 400
    user, err = _self_only(user_id)
    if err:
        return err
    if section not in RESUME_AI_SECTIONS:
        return jsonify({"success": False, "code": "bad_section",
                        "message": "不支持的简历段落"}), 400
    if isinstance(draft, str) and len(draft) > RESUME_AI_SECTION_MAX_LEN:
        return jsonify({"success": False, "code": "draft_too_long",
                        "message": "内容过长，请精简后再试"}), 400

    if rate_limited('resume-ai:' + client_key(), RESUME_AI_RATE_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "AI 使用过于频繁，请稍后再试"}), 429

    if not ai.client.ai_configured():
        return jsonify({"success": False, "code": "ai_not_configured",
                        "message": "AI 辅助功能尚未启用，请联系管理员（12316）"}), 503

    profile = employment.get_learner_profile(user_id)
    material = profile_for_ai(profile)
    label = RESUME_AI_SECTIONS[section]

    resume = employment.get_resume(user_id) or {}
    own_input = ''
    if section == 'experience':
        exp = resume.get('experience') or []
        if isinstance(exp, list) and exp:
            own_input = '\n'.join(
                '- %s / %s / %s：%s' % (e.get('company') or '', e.get('position') or '',
                                        e.get('period') or '', (e.get('desc') or '').strip())
                for e in exp if isinstance(e, dict))
    elif isinstance(draft, str):
        own_input = draft.strip()

    user_prompt = '【学员真实数据（唯一可用事实来源）】\n%s\n' % material
    if own_input:
        user_prompt += '\n【学员本人已填写的原文（可在不改变事实的前提下润色）】\n%s\n' % own_input
    elif section != 'experience':
        user_prompt += '\n【学员本人已填写的原文】（暂无，请完全基于上面的真实数据来写）\n'
    user_prompt += '\n请撰写「%s」这一段。' % label

    try:
        text = call_ai_service(
            RESUME_AI_SYSTEM_PROMPT, user_prompt,
            temperature=0.4, max_tokens=600 + AI_REASONING_TOKEN_RESERVE)
    except Exception as e:
        logger.warning('简历 AI 生成失败: %s', e)
        return jsonify({"success": False, "code": "ai_unavailable",
                        "message": "AI 服务暂时不可用，请稍后重试"}), 503

    if not text or not str(text).strip():
        return jsonify({"success": False, "code": "ai_unavailable",
                        "message": "AI 没有返回内容，请稍后重试"}), 503

    employment.mark_resume_ai_used(user_id)
    return jsonify({
        "success": True,
        "section": section,
        "section_label": label,
        "text": str(text).strip(),
        "notice": "本段由 AI 根据你的平台学习数据起草，请核对其中的每一项事实后再用于投递。",
    })


@employment_profile_bp.route('/api/employment/intent', methods=['POST'])
def add_job_intent():
    """登记对某条公开招聘公告的求职意向（幂等）。

    ⚠️ 平台**不是**官方报名系统：这里只记录意向，**不代表报名成功**。
    前端的成功提示与公告详情页都必须写明「请按公告原文自行报名」。
    """
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    recruit_key = (data.get('recruit_key') or '').strip()
    note = data.get('note') or ''

    if not user_id or not recruit_key:
        return jsonify({"success": False, "code": "bad_request", "message": "参数不完整"}), 400
    user, err = _self_only(user_id)
    if err:
        return err
    if recruitments_db.get_recruitment(recruit_key) is None:
        return jsonify({"success": False, "code": "not_found",
                        "message": "公告不存在或已下架"}), 404

    created = employment.add_job_intent(user_id, recruit_key, note)
    return jsonify({
        "success": True,
        "created": created,
        "message": "已记录求职意向" if created else "意向备注已更新",
        "notice": "本平台不代办报名，请按公告原文的要求和时间自行报名。",
    })


@employment_profile_bp.route('/api/employment/intent', methods=['DELETE'])
def remove_job_intent():
    """取消求职意向登记。"""
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    recruit_key = (data.get('recruit_key') or '').strip()
    if not user_id or not recruit_key:
        return jsonify({"success": False, "code": "bad_request", "message": "参数不完整"}), 400
    user, err = _self_only(user_id)
    if err:
        return err
    removed = employment.remove_job_intent(user_id, recruit_key)
    return jsonify({"success": True, "removed": removed,
                    "message": "已取消意向登记" if removed else "未找到该意向记录"})


@employment_profile_bp.route('/api/employment/my-jobs/<user_id>', methods=['GET'])
def get_my_jobs(user_id):
    """「我的求职」聚合：企业岗位投递 + 公开招聘意向。

    两条通道在数据结构上完全不同（前者挂在数字 job_id 上、后者挂在公告字符串 key 上），
    这里统一成前端可直接渲染的两组，并**如实标注通道类型**。
    """
    user, err = _self_only(user_id)
    if err:
        return err

    applications = employment.get_user_applications(user_id)
    for a in applications:
        a['channel'] = 'enterprise'

    # 意向记录只有 recruit_key，这里补上公告的标题/单位/地区/报名截止，
    # 并对**已从招募表里移除**的公告做剪枝（否则会渲染出一条点不开的空卡）。
    intents = []
    for it in employment.get_job_intents(user_id):
        rec = recruitments_db.get_recruitment(it['recruit_key'])
        if not rec:
            continue
        intents.append({
            'channel': 'public_recruit',
            'recruit_key': it['recruit_key'],
            'note': it['note'],
            'created_at': it['created_at'],
            'title': rec.get('title') or '',
            'org': rec.get('org') or '',
            'region': rec.get('region') or '',
            'category': rec.get('category') or '',
            'deadline': rec.get('deadline') or '',
            'status': rec.get('status') or 'unknown',
            'status_label': rec.get('status_label') or '',
        })

    return jsonify({
        "success": True,
        "applications": applications,
        "intents": intents,
        "intent_notice": recruitments_db.get_recruitment_notes()['disclaimer'],
        # ⚠️ 平台**不强制**先写简历才能投递（投递只记一条申请 + 给积分），
        # 但企业端看到的是「无简历的空申请」。这里如实下发简历状态，
        # 前端据此给出持久提示 —— 而不是让文案和实际行为互相打架（2026-10-07）。
        "has_resume": user_has_resume(user_id),
    })
