from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.onboarding.service import (
    ONBOARDING_OUTCOMES,
    ROLE_PORTALS,
    complete_onboarding,
    needs_onboarding,
)
from app.session_manager import load_session


onboarding_bp = Blueprint(
    "onboarding",
    __name__,
    url_prefix="/api/onboarding",
)


def _session_for_portal(portal: str) -> dict | None:
    session = load_session(required=True, allowed_states={"active"})
    if ROLE_PORTALS.get(session["role"]) != portal:
        return None
    return session


@onboarding_bp.get("/<portal>")
def get_onboarding_state(portal: str):
    session = _session_for_portal(portal)
    if session is None:
        return jsonify(success=False, message="无权访问该门户引导"), 403

    return jsonify(
        success=True,
        required=needs_onboarding(int(session["id"]), portal),
        portal=portal,
    )


@onboarding_bp.post("/<portal>/complete")
def complete_portal_onboarding(portal: str):
    session = _session_for_portal(portal)
    if session is None:
        return jsonify(success=False, message="无权访问该门户引导"), 403

    payload = request.get_json(silent=True)
    outcome = payload.get("outcome") if isinstance(payload, dict) else None
    if outcome not in ONBOARDING_OUTCOMES:
        return jsonify(
            success=False,
            errors={"outcome": "outcome 必须为 completed 或 skipped"},
        ), 400

    complete_onboarding(int(session["id"]), portal, outcome)
    return jsonify(success=True, portal=portal, outcome=outcome)
