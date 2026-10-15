#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""直播实训域：朗读实录分析、观众提问、三类实训提交与记录查询。

T13 从 app.py 的「直播实训」区块整体迁出。按 spec 的「单个领域路由文件不超过
600 行」在域内再分模块，共用同一个蓝图对象 live_bp（与 domains/agriculture、
domains/pest 同构：一个目录放两个蓝图对象会让 T01 检查器把该目录按容器处理，
误判成两个域）。

依赖都在共享层，不反向 import 任何领域：
  - 作物白名单与校验   shared.ec_products.ec_product_ok
  - 朗读评分纯函数     shared.live_reading（汉字抽取 / 语速折算 / 必卖点 rubric）
  - 上游调用           ai.client
  - 限流与取用户       core.session
实训落库经 database 契约层（db_domains/teaching.py 那批函数）。
"""

import json

import logging

from flask import Blueprint, jsonify, request

import re

from ai.client import AI_REASONING_TOKEN_RESERVE, chat_completion, chat_model
from core.session import client_key, get_session_user, rate_limited
from shared.ec_products import (
    EC_COPY_MAX_LEN,
    EC_CS_TRANSCRIPT_MAX_TURNS,
    EC_CS_TURN_MAX_LEN,
    EC_LIVE_TRANSCRIPT_MAX_LEN,
    EC_RATE_COMMENTS_LIMIT,
    EC_SCRIPT_MAX_LEN,
    ec_product_ok,
)
from shared.live_reading import LIVE_RUBRIC_RE, LIVE_SPEED_IDEAL, live_cjk, live_speed_score
from shared.training_status import training_status_label
from db_domains import teaching

# 本域读这些能力域的数据，显式声明供 tools/check_architecture.py 判权。
CAPABILITIES_USED = ('teaching.read',)

live_bp = Blueprint('live_training', __name__)

logger = logging.getLogger(__name__)


@live_bp.route('/api/ecommerce/live/report', methods=['POST'])
def live_reading_report():
    """朗读实录分析：把「学员现场说了什么」变成可复现的指标（EC3/EC4）。

    与 `/api/ecommerce/feedback` 的分工：
      · feedback 评的是**稿子的文本质量**；
      · 本接口评的是**学员朗读时的实际表现** —— 完成度 / 真实语速 / 必卖点命中 / 冷场。
    不调用 AI、不含随机数：同样的输入必然得到同样的输出。
    """
    data = request.get_json() or {}
    script = str(data.get('script', '') or '')
    transcript = str(data.get('transcript', '') or '')

    def _f(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0

    duration = _f(data.get('duration_sec'))
    max_silence = _f(data.get('max_silence_sec'))

    if not transcript.strip():
        return jsonify({"success": False, "code": "empty_transcript",
                        "message": "还没有识别到朗读内容"}), 400
    if len(transcript) > EC_LIVE_TRANSCRIPT_MAX_LEN:
        return jsonify({"success": False, "code": "transcript_too_long",
                        "message": "朗读内容过长"}), 400

    # ① 完成度：稿子里的汉字被念出来的比例（按字去重，避免重复朗读刷分）
    script_chars = set(live_cjk(script))
    said_chars = set(live_cjk(transcript))
    missed_chars = script_chars - said_chars
    coverage = round(len(script_chars & said_chars) * 100.0 / len(script_chars)) if script_chars else 0

    # ② 真实语速
    spoken_chars = len(live_cjk(transcript))
    cpm = round(spoken_chars / (duration / 60.0)) if duration > 0 else 0
    speed_score = live_speed_score(cpm)

    # ③ 必卖点命中 —— 逐项给出「稿里有没有 / 嘴上有没有」
    items = []
    hit = 0
    for name, rx in LIVE_RUBRIC_RE:
        in_script = bool(rx.search(script))
        said = bool(rx.search(transcript))
        items.append({"name": name, "in_script": in_script, "said": said})
        if said:
            hit += 1
    rubric_score = round(hit * 100.0 / len(LIVE_RUBRIC_RE))

    # ④ 冷场
    silence_penalty = 15 if max_silence >= 10 else (8 if max_silence >= 6 else 0)

    overall = max(0, min(100, round(rubric_score * 0.5 + coverage * 0.3 + speed_score * 0.2)
                         - silence_penalty))

    tips = []
    for it in items:
        if it['in_script'] and not it['said']:
            tips.append('稿子里写了「%s」但朗读时没有说出来' % it['name'])
        elif not it['in_script']:
            tips.append('稿子里缺少「%s」这一项' % it['name'])
    if missed_chars:
        tips.append('稿子里有 %d 个字没有念到' % len(missed_chars))
    if cpm and cpm < LIVE_SPEED_IDEAL[0]:
        tips.append('语速偏慢（约 %d 字/分钟），可适当加快' % cpm)
    elif cpm > LIVE_SPEED_IDEAL[1]:
        tips.append('语速偏快（约 %d 字/分钟），注意留出停顿' % cpm)
    if max_silence >= 6:
        tips.append('最长冷场约 %.1f 秒；直播中超过 5 秒不说话，观众容易流失' % max_silence)

    return jsonify({"success": True, "report": {
        "coverage": coverage,
        "missed_chars": len(missed_chars),
        "spoken_chars": spoken_chars,
        "duration_sec": round(duration, 1),
        "speed_cpm": cpm,
        "speed_score": speed_score,
        "rubric_score": rubric_score,
        "rubric_hit": hit,
        "rubric_total": len(LIVE_RUBRIC_RE),
        "rubric_items": items,
        "max_silence_sec": round(max_silence, 1),
        "silence_penalty": silence_penalty,
        "overall_score": overall,
        "tips": tips[:5],
        "source": "rule",
        "source_note": "本组指标由规则分析给出（可复现），不含 AI 评分。"
    }})


@live_bp.route('/api/ecommerce/live/comments', methods=['POST'])
def live_ai_comments():
    """观众提问（2026-10-05 直播间进阶·题库化）：按学员刚说的内容生成 1-2 条针对性提问。

    走 `chat_model()`；失败或限流时由前端回退到规则评论池（本接口不返回兜底，
    由前端决定，避免「AI 失败却拿到看似正常的评论」不可见）。
    """
    data = request.get_json() or {}
    speech = str(data.get('speech', '') or '').strip()[:300]
    difficulty = str(data.get('difficulty', '') or '新手').strip()[:8] or '新手'

    if rate_limited('ec-comments:' + client_key(), EC_RATE_COMMENTS_LIMIT):
        return jsonify({"success": False, "code": "rate_limited",
                        "message": "请求过于频繁，请稍后再试"}), 429
    if not speech:
        return jsonify({"success": False, "code": "empty_speech",
                        "message": "没有收到主播说的话"}), 400

    tone = {
        '新手': '友善、好奇，顺着主播的话提问',
        '进阶': '会比较、会质疑（比价、追问依据）',
        '挑战': '挑剔甚至带攻击性，可能提售后维权、要求看检测报告',
    }.get(difficulty, '友善、好奇')

    try:
        result = chat_completion(
            messages=[
                {"role": "system", "content":
                    "你是农产品直播间的观众。根据主播刚说的话，生成 1-2 条你会发的弹幕提问，"
                    "语气要求：" + tone + "。只输出严格 JSON：{\"comments\":[\"...\",\"...\"]}，"
                    "每条不超过 30 字，不要输出其他文字。"},
                {"role": "user", "content": "主播刚说：「" + speech + "」"},
            ],
            temperature=0.8,
            max_tokens=120 + AI_REASONING_TOKEN_RESERVE,
            timeout=20,
            model=chat_model()
        )
        m = re.search(r'\{.*?\}', result, re.DOTALL)
        obj = json.loads(m.group()) if m else {}
        comments = [str(c).strip()[:60] for c in (obj.get('comments') or []) if str(c).strip()][:2]
        if comments:
            return jsonify({"success": True, "comments": comments, "source": "ai"})
        return jsonify({"success": False, "code": "ai_empty",
                        "message": "上游未返回有效评论"}), 503
    except Exception as e:
        logger.error(f"观众提问生成失败: {e}")
        return jsonify({"success": False, "code": "ai_unavailable",
                        "message": "AI 评论暂不可用"}), 503


# 实训提交状态的中文标签：唯一实现在共享层 shared.training_status。
# 教师端（教学支撑域）的实训提交列表也要用它，而领域之间不得互相 import，
# 因此上提共享层，两边从同一份查表取，避免两套状态文案各自漂移。
_training_status_label = training_status_label


def _training_submit_core(kind):
    """把一次实训落库到既有作业链路（EC7 + 2026-10-05 文案/客服闭环）。

    kind ∈ {'live','copy','cs'}：落点都是 `assignments` + `assignment_submissions`，
    只以题目 title 前缀区分（见 teaching.TRAINING_TITLE_FMTS）。
    需要登录；同一学员同一作物同一 kind 只保留最新一次提交，attempts 递增。
    """
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "code": "login_required",
                        "message": "登录后即可保存实训记录"}), 401

    data = request.get_json() or {}
    product = str(data.get('product', '') or '').strip()
    if kind == 'cs':
        # 客服对练的产品是自由文本（学员可自填，如「增城桂味荔枝」），
        # 与模拟对话接口 `simulate_customer_service` 的口径一致：不做白名单，
        # 只做非空 + 长度校验，避免 prompt 注入面并防止作业标题无限膨胀。
        if not product:
            return jsonify({"success": False, "code": "empty_product",
                            "message": "请填写产品名称"}), 400
        product = product[:30]
    else:
        if not ec_product_ok(product):
            return jsonify({"success": False, "code": "unknown_product",
                            "message": "暂不支持该农产品，请从列表中选择"}), 400

    meta = data.get('meta') if isinstance(data.get('meta'), dict) else {}
    payload = {"type": kind + "_training", "product": product, "meta": meta}

    if kind == 'cs':
        transcript = data.get('transcript')
        if not isinstance(transcript, list) or not transcript:
            return jsonify({"success": False, "code": "empty_transcript",
                            "message": "请先完成至少一轮对话再提交"}), 400
        turns = []
        for t in transcript[:EC_CS_TRANSCRIPT_MAX_TURNS]:
            if not isinstance(t, dict):
                continue
            turns.append({
                "role": str(t.get('role', '') or '')[:12],
                "content": str(t.get('content', '') or '')[:EC_CS_TURN_MAX_LEN],
            })
        if not turns:
            return jsonify({"success": False, "code": "empty_transcript",
                            "message": "对话记录为空"}), 400
        payload['transcript'] = turns
        score_raw = data.get('score')
    else:
        script = str(data.get('script', '') or '')
        cap = EC_COPY_MAX_LEN if kind == 'copy' else EC_SCRIPT_MAX_LEN
        if not script.strip():
            return jsonify({"success": False, "code": "empty_script",
                            "message": "请先写出或生成你的内容"}), 400
        if len(script) > cap:
            return jsonify({"success": False, "code": "script_too_long",
                            "message": f"内容过长，请控制在 {cap} 字以内"}), 400
        payload['script'] = script
        if kind == 'live':
            fb = data.get('feedback') if isinstance(data.get('feedback'), dict) else {}
            rp = data.get('report') if isinstance(data.get('report'), dict) else {}
            payload['feedback'] = fb
            payload['report'] = rp
            score_raw = fb.get('overall_score')
        else:
            score_raw = data.get('score')

    try:
        overall = int(score_raw or 0)
    except (TypeError, ValueError):
        overall = 0

    student_id = str(user.get('username') or user.get('id') or '')
    if not student_id:
        return jsonify({"success": False, "code": "login_required",
                        "message": "登录后即可保存实训记录"}), 401

    aid = teaching.get_or_create_training_assignment(product, kind)
    sid, attempts = teaching.save_live_training(aid, student_id, payload, overall)
    # ⚠️ 只回 rule_score（系统规则分）。score 列现在是**教师批改分**，
    #    提交接口不该回一个自己刚算出来的规则分冒充「分数」。
    return jsonify({"success": True, "submission_id": sid, "assignment_id": aid,
                    "attempts": attempts, "rule_score": overall})


@live_bp.route('/api/ecommerce/live/submit', methods=['POST'])
def submit_live_training():
    """直播带货实训提交（话术稿 + 评分 + 朗读实录），需要登录。"""
    return _training_submit_core('live')


@live_bp.route('/api/ecommerce/copy/submit', methods=['POST'])
def submit_copy_training():
    """商品文案实训提交（学员改写的「我的稿」），需要登录。"""
    return _training_submit_core('copy')


@live_bp.route('/api/ecommerce/cs/submit', methods=['POST'])
def submit_cs_training():
    """客服对练实训提交（完整对话记录 + 规则评分），需要登录。"""
    return _training_submit_core('cs')


@live_bp.route('/api/ecommerce/live/records', methods=['GET'])
def get_my_live_trainings():
    """当前登录学员的实训记录（每个作物一条）。

    `?kind=` 可取 live（默认）/ copy / cs；只认 teaching.TRAINING_TITLE_FMTS 里的键。
    """
    user = get_session_user()
    if not user:
        return jsonify({"success": False, "code": "login_required",
                        "message": "登录后可查看实训记录"}), 401
    student_id = str(user.get('username') or user.get('id') or '')
    kind = str(request.args.get('kind', '') or 'live').strip()
    if kind not in teaching.TRAINING_TITLE_FMTS:
        kind = 'live'
    rows = teaching.get_trainings(student_id, kind)
    out = []
    for r in rows:
        try:
            detail = json.loads(r.get('content') or '{}')
        except Exception:
            detail = {}
        out.append({
            "id": r.get('id'),
            "assignment_title": r.get('assignment_title'),
            "product": detail.get('product'),
            # score = 教师批改分（未批改为 None）；系统规则分单独给 rule_score，
            # 两者不能混为一谈（2026-10-07 前 score 被规则分占用，学员端把规则分当成了最终成绩）。
            "score": r.get('score'),
            "rule_score": detail.get('rule_score'),
            "status": r.get('status'),
            "status_label": _training_status_label(r.get('status')),
            "attempts": detail.get('attempts', 1),
            "submitted_at": r.get('submitted_at'),
            "graded_at": r.get('graded_at'),
            "feedback": r.get('feedback') or '',
            "report": detail.get('report') or {},
            "feedback_detail": detail.get('feedback') or {},
            "meta": detail.get('meta') or {},
        })
    return jsonify({"success": True, "records": out, "kind": kind})


__all__ = ['live_bp']
