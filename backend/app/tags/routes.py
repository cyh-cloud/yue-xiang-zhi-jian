from __future__ import annotations

from flask import Blueprint, jsonify

from app.tags.service import list_interest_tags


interest_tags_bp = Blueprint(
    "interest_tags",
    __name__,
    url_prefix="/api/interest-tags",
)


@interest_tags_bp.get("")
def get_interest_tags():
    return jsonify(success=True, tags=list_interest_tags())
