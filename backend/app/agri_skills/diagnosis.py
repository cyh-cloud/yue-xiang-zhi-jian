from __future__ import annotations

import json
from datetime import datetime, timedelta

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.agri_skills.errors import (
    AgriNotFoundError,
    AgriValidationError,
    AiUnavailableError,
)
from app.agri_skills.presets import get_preset_provider
from app.db import get_db
from app.session_manager import utc_now_iso


INPUT_MODES = {"text", "voice"}
ALLOWED_AI_STATUSES = {"follow_up_required", "conclusion_ready"}
FOLLOWUP_OUTCOMES = {"improved", "unchanged", "worsened"}
MAX_DIAGNOSIS_ROUNDS = 5
AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"


def _deserialize_json(value, expected_type):
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, expected_type) else None


def _load_diagnosis(user_id: int, session_id: int) -> dict:
    row = get_db().execute(
        """
        SELECT
            id, user_id, product_key, affected_part, symptoms_json,
            status, round_count, conclusion_json, limited,
            pending_question, pending_question_round,
            source_session_id, source_followup_id,
            created_at, updated_at, abandoned_at
        FROM agri_diagnosis_sessions
        WHERE id = ? AND user_id = ?
        """,
        (session_id, user_id),
    ).fetchone()
    if row is None:
        raise AgriNotFoundError("诊断记录不存在")

    answer_rows = get_db().execute(
        """
        SELECT
            id, round_no, question, answer, input_mode, ai_status, created_at
        FROM agri_diagnosis_answers
        WHERE session_id = ?
        ORDER BY round_no, id
        """,
        (session_id,),
    ).fetchall()
    answer_records = [
        {
            "id": int(answer["id"]),
            "round_no": int(answer["round_no"]),
            "question": str(answer["question"]),
            "answer": str(answer["answer"]),
            "input_mode": str(answer["input_mode"]),
            "ai_status": str(answer["ai_status"]),
            "created_at": str(answer["created_at"]),
        }
        for answer in answer_rows
    ]
    followup_rows = get_db().execute(
        """
        SELECT id, outcome, note, created_at
        FROM agri_diagnosis_followups
        WHERE session_id = ?
        ORDER BY created_at, id
        """,
        (session_id,),
    ).fetchall()
    followups = [
        {
            "id": int(followup["id"]),
            "outcome": str(followup["outcome"]),
            "note": str(followup["note"]),
            "created_at": str(followup["created_at"]),
        }
        for followup in followup_rows
    ]

    product_key = str(row["product_key"])
    product = get_preset_provider().get_product(product_key)
    if product is None:
        product = {
            "key": product_key,
            "name": product_key,
            "sort_order": None,
            "available": False,
        }

    symptoms = _deserialize_json(str(row["symptoms_json"]), list) or []
    conclusion = (
        _deserialize_json(str(row["conclusion_json"]), dict)
        if row["conclusion_json"] is not None
        else None
    )
    pending_question = (
        str(row["pending_question"])
        if row["pending_question"] is not None
        else None
    )
    questions = [answer["question"] for answer in answer_records]
    if pending_question:
        questions.append(pending_question)

    source_session_id = (
        int(row["source_session_id"])
        if row["source_session_id"] is not None
        else None
    )
    source_followup_id = (
        int(row["source_followup_id"])
        if row["source_followup_id"] is not None
        else None
    )
    source_available = True
    source_context = None
    if source_session_id is not None:
        source_available = False
        source_row = get_db().execute(
            """
            SELECT
                source.conclusion_json,
                followup.outcome,
                followup.note
            FROM agri_diagnosis_sessions AS source
            JOIN agri_diagnosis_followups AS followup
              ON followup.id = ?
             AND followup.session_id = source.id
            WHERE source.id = ? AND source.user_id = ?
            """,
            (source_followup_id, source_session_id, user_id),
        ).fetchone()
        if source_row is not None:
            source_available = True
            source_context = {
                "source_conclusion": (
                    _deserialize_json(
                        str(source_row["conclusion_json"]),
                        dict,
                    )
                    if source_row["conclusion_json"] is not None
                    else None
                ),
                "followup_status": str(source_row["outcome"]),
                "followup_note": str(source_row["note"]),
            }

    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "product": product,
        "product_key": product_key,
        "affected_part": str(row["affected_part"]),
        "symptoms": [str(item) for item in symptoms],
        "status": str(row["status"]),
        "round_count": int(row["round_count"]),
        "conclusion": conclusion,
        "limited": bool(row["limited"]),
        "pending_question": pending_question,
        "pending_question_round": (
            int(row["pending_question_round"])
            if row["pending_question_round"] is not None
            else None
        ),
        "questions": questions,
        "answers": [answer["answer"] for answer in answer_records],
        "answer_records": answer_records,
        "followups": followups,
        "source_session_id": source_session_id,
        "source_followup_id": source_followup_id,
        "source_available": source_available,
        "source_context": source_context,
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "abandoned_at": (
            str(row["abandoned_at"])
            if row["abandoned_at"] is not None
            else None
        ),
    }


def get_diagnosis(user_id: int, session_id: int) -> dict:
    expire_inactive_diagnoses(utc_now_iso())
    return _load_diagnosis(user_id, session_id)


def list_diagnoses(user_id: int) -> list[dict]:
    expire_inactive_diagnoses(utc_now_iso())
    rows = get_db().execute(
        """
        SELECT id
        FROM agri_diagnosis_sessions
        WHERE user_id = ?
        ORDER BY updated_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return [_load_diagnosis(user_id, int(row["id"])) for row in rows]


def _validate_ai_turn(
    payload: dict,
    *,
    forced_limited: bool,
    context: dict,
) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    status = payload.get("status")

    if forced_limited:
        conclusion = payload.get("conclusion")
        if (
            not isinstance(conclusion, dict)
            or not str(conclusion.get("cause", "")).strip()
            or not str(conclusion.get("treatment", "")).strip()
        ):
            conclusion = {
                "cause": (
                    f"现有信息提示需要重点排查{context['product']['name']}"
                    f"{context['affected_part']}的"
                    f"{'、'.join(context['symptoms'])}问题"
                ),
                "treatment": (
                    "建议清理异常部位并持续观察，记录症状变化，"
                    "结合当地农技人员意见开展规范防治。"
                ),
            }
        else:
            conclusion = {
                "cause": str(conclusion["cause"]).strip(),
                "treatment": str(conclusion["treatment"]).strip(),
            }
        return {
            "status": "conclusion_ready",
            "question": None,
            "conclusion": conclusion,
            "limited": True,
        }

    if status not in ALLOWED_AI_STATUSES:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    if status == "follow_up_required":
        question = str(payload.get("question", "")).strip()
        if not question:
            raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
        return {
            "status": status,
            "question": question,
            "conclusion": None,
            "limited": False,
        }

    conclusion = payload.get("conclusion")
    if (
        not isinstance(conclusion, dict)
        or not str(conclusion.get("cause", "")).strip()
        or not str(conclusion.get("treatment", "")).strip()
    ):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
    return {
        "status": status,
        "question": None,
        "conclusion": {
            "cause": str(conclusion["cause"]).strip(),
            "treatment": str(conclusion["treatment"]).strip(),
        },
        "limited": False,
    }


def _store_ai_turn(user_id: int, session_id: int, result: dict) -> dict:
    current = _load_diagnosis(user_id, session_id)
    now = utc_now_iso()
    with get_db():
        if result["status"] == "follow_up_required":
            next_round = current["round_count"] + 1
            if next_round > MAX_DIAGNOSIS_ROUNDS:
                raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)
            get_db().execute(
                """
                UPDATE agri_diagnosis_sessions
                SET
                    pending_question = ?,
                    pending_question_round = ?,
                    updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'in_progress'
                """,
                (
                    result["question"],
                    next_round,
                    now,
                    session_id,
                    user_id,
                ),
            )
        else:
            get_db().execute(
                """
                UPDATE agri_diagnosis_sessions
                SET
                    status = 'completed',
                    conclusion_json = ?,
                    limited = ?,
                    pending_question = NULL,
                    pending_question_round = NULL,
                    updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'in_progress'
                """,
                (
                    json.dumps(result["conclusion"], ensure_ascii=False),
                    int(result["limited"]),
                    now,
                    session_id,
                    user_id,
                ),
            )
    return _load_diagnosis(user_id, session_id)


def start_diagnosis(user_id: int, session_id: int) -> dict:
    current = get_diagnosis(user_id, session_id)
    if current["status"] != "in_progress":
        return current
    if current["pending_question"]:
        return current

    round_no = current["round_count"] + 1
    ai_context = {
        "product_name": current["product"]["name"],
        "affected_part": current["affected_part"],
        "symptoms": current["symptoms"],
        "round_no": round_no,
        "prior_questions": current["questions"],
        "prior_answers": current["answers"],
    }
    if current["source_context"] is not None:
        ai_context.update(current["source_context"])
    try:
        result = _validate_ai_turn(
            get_ai_client().complete_json(
                build_ai_messages(
                    "diagnosis_turn",
                    ai_context,
                ),
                call_point="diagnosis_turn",
            ),
            forced_limited=False,
            context=current,
        )
    except AiUnavailableError:
        return {
            **_load_diagnosis(user_id, session_id),
            "ai_error": AI_UNAVAILABLE_MESSAGE,
        }
    return _store_ai_turn(user_id, session_id, result)


def _persist_diagnosis_turn(
    user_id: int,
    current: dict,
    answer: str,
    input_mode: str,
    result: dict,
) -> dict:
    round_no = current["pending_question_round"]
    question = current["pending_question"]
    if (
        not isinstance(round_no, int)
        or question is None
        or not 1 <= round_no <= MAX_DIAGNOSIS_ROUNDS
    ):
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    now = utc_now_iso()
    with get_db():
        get_db().execute(
            """
            INSERT INTO agri_diagnosis_answers (
                session_id, round_no, question, answer, input_mode,
                ai_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                current["id"],
                round_no,
                question,
                answer,
                input_mode,
                result["status"],
                now,
            ),
        )
        if result["status"] == "conclusion_ready":
            get_db().execute(
                """
                UPDATE agri_diagnosis_sessions
                SET
                    status = 'completed',
                    round_count = ?,
                    conclusion_json = ?,
                    limited = ?,
                    pending_question = NULL,
                    pending_question_round = NULL,
                    updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'in_progress'
                """,
                (
                    round_no,
                    json.dumps(result["conclusion"], ensure_ascii=False),
                    int(result["limited"]),
                    now,
                    current["id"],
                    user_id,
                ),
            )
        else:
            next_round = round_no + 1
            get_db().execute(
                """
                UPDATE agri_diagnosis_sessions
                SET
                    round_count = ?,
                    pending_question = ?,
                    pending_question_round = ?,
                    updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'in_progress'
                """,
                (
                    round_no,
                    result["question"],
                    next_round,
                    now,
                    current["id"],
                    user_id,
                ),
            )
    return {
        **result,
        "session": _load_diagnosis(user_id, current["id"]),
    }


def answer_diagnosis(
    user_id: int,
    session_id: int,
    answer: str,
    input_mode: str,
) -> dict:
    if input_mode not in INPUT_MODES:
        raise AgriValidationError(
            "输入方式无效",
            details={"input_mode": "输入方式无效"},
        )
    answer_text = str(answer).strip()
    if not answer_text:
        raise AgriValidationError(
            "回答不能为空",
            details={"answer": "回答不能为空"},
        )

    current = get_diagnosis(user_id, session_id)
    if current["status"] != "in_progress":
        raise AgriValidationError("诊断会话不可继续")
    if not current["pending_question"]:
        current = start_diagnosis(user_id, session_id)
    if not current["pending_question"]:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE)

    result = _validate_ai_turn(
        get_ai_client().complete_json(
            build_ai_messages(
                "diagnosis_turn",
                {
                    "product_name": current["product"]["name"],
                    "affected_part": current["affected_part"],
                    "symptoms": current["symptoms"],
                    "round_no": current["pending_question_round"],
                    "prior_questions": current["questions"],
                    "prior_answers": current["answers"],
                },
            ),
            call_point="diagnosis_turn",
        ),
        forced_limited=current["round_count"] >= MAX_DIAGNOSIS_ROUNDS - 1,
        context=current,
    )
    return _persist_diagnosis_turn(
        user_id,
        current,
        answer_text,
        input_mode,
        result,
    )


def create_diagnosis(
    user_id: int,
    product_key: str,
    affected_part: str,
    symptoms: list[str],
) -> dict:
    product = get_preset_provider().get_product(product_key)
    if product is None:
        raise AgriValidationError(
            "产品不存在",
            details={"product_key": "产品不存在"},
        )

    normalized_part = str(affected_part or "").strip()
    normalized_symptoms = (
        list(
            dict.fromkeys(
                str(item).strip()
                for item in symptoms
                if str(item).strip()
            )
        )
        if isinstance(symptoms, list)
        else []
    )
    if not normalized_part:
        raise AgriValidationError(
            "发病部位不能为空",
            details={"affected_part": "不能为空"},
        )
    if not normalized_symptoms:
        raise AgriValidationError(
            "至少选择一个症状",
            details={"symptoms": "至少选择一个症状"},
        )

    now = utc_now_iso()
    with get_db():
        cursor = get_db().execute(
            """
            INSERT INTO agri_diagnosis_sessions (
                user_id, product_key, affected_part, symptoms_json,
                status, round_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'in_progress', 0, ?, ?)
            """,
            (
                user_id,
                product_key,
                normalized_part,
                json.dumps(normalized_symptoms, ensure_ascii=False),
                now,
                now,
            ),
        )
    return start_diagnosis(user_id, int(cursor.lastrowid))


def add_followup(
    user_id: int,
    session_id: int,
    outcome: str,
    note: object,
) -> dict:
    session = get_diagnosis(user_id, session_id)
    if session["status"] != "completed":
        raise AgriValidationError("仅已完成诊断可记录复诊")
    if outcome not in FOLLOWUP_OUTCOMES:
        raise AgriValidationError(
            "复诊状态不正确",
            details={"outcome": "状态不正确"},
        )
    normalized_note = str(note or "").strip()
    now = utc_now_iso()
    with get_db():
        cursor = get_db().execute(
            """
            INSERT INTO agri_diagnosis_followups (
                session_id, outcome, note, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (session_id, outcome, normalized_note, now),
        )
    return {
        "id": int(cursor.lastrowid),
        "outcome": outcome,
        "note": normalized_note,
        "created_at": now,
    }


def list_followups(user_id: int, session_id: int) -> list[dict]:
    get_diagnosis(user_id, session_id)
    rows = get_db().execute(
        """
        SELECT id, outcome, note, created_at
        FROM agri_diagnosis_followups
        WHERE session_id = ?
        ORDER BY created_at, id
        """,
        (session_id,),
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "outcome": str(row["outcome"]),
            "note": str(row["note"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def create_diagnosis_from_followup(
    user_id: int,
    diagnosis_session_id: int,
    followup_id: int,
) -> dict:
    source = get_diagnosis(user_id, diagnosis_session_id)
    followup = get_db().execute(
        """
        SELECT id
        FROM agri_diagnosis_followups
        WHERE id = ? AND session_id = ?
        """,
        (followup_id, diagnosis_session_id),
    ).fetchone()
    if followup is None:
        raise AgriNotFoundError("复诊记录不存在")

    now = utc_now_iso()
    with get_db():
        cursor = get_db().execute(
            """
            INSERT INTO agri_diagnosis_sessions (
                user_id, product_key, affected_part, symptoms_json,
                status, round_count, source_session_id, source_followup_id,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'in_progress', 0, ?, ?, ?, ?)
            """,
            (
                user_id,
                source["product_key"],
                source["affected_part"],
                json.dumps(source["symptoms"], ensure_ascii=False),
                diagnosis_session_id,
                followup_id,
                now,
                now,
            ),
        )
    return start_diagnosis(user_id, int(cursor.lastrowid))


def abandon_diagnosis(user_id: int, session_id: int) -> dict:
    current = get_diagnosis(user_id, session_id)
    if current["status"] == "abandoned":
        return current
    if current["status"] != "in_progress":
        raise AgriValidationError("诊断会话不可放弃")

    now = utc_now_iso()
    with get_db():
        get_db().execute(
            """
            UPDATE agri_diagnosis_sessions
            SET
                status = 'abandoned',
                pending_question = NULL,
                pending_question_round = NULL,
                abandoned_at = ?,
                updated_at = ?
            WHERE id = ? AND user_id = ? AND status = 'in_progress'
            """,
            (now, now, session_id, user_id),
        )
    return _load_diagnosis(user_id, session_id)


def expire_inactive_diagnoses(now_iso: str) -> int:
    try:
        now = datetime.fromisoformat(now_iso)
    except (TypeError, ValueError) as error:
        raise AgriValidationError("时间格式无效") from error
    cutoff = (now - timedelta(days=365)).isoformat()
    with get_db():
        result = get_db().execute(
            """
            UPDATE agri_diagnosis_sessions
            SET
                status = 'abandoned',
                abandoned_at = ?,
                updated_at = ?
            WHERE status = 'in_progress' AND updated_at <= ?
            """,
            (now_iso, now_iso, cutoff),
        )
    return int(result.rowcount)
