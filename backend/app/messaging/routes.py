from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.messaging.notification_service import list_notifications
from app.messaging.relationships import list_allowed_contacts
from app.messaging.service import (
    ConversationNotFoundError,
    MessageNotFoundError,
    MessageValidationError,
    MessagingAccessDeniedError,
    clear_read_items,
    get_conversation_messages,
    get_message_summary,
    list_conversations,
    mark_all_read,
    mark_notification_read,
    mark_private_message_read,
    reply_to_conversation,
    send_private_message,
)
from app.session_manager import load_session


messages_bp = Blueprint("messages", __name__, url_prefix="/api/messages")


def _active_session() -> dict:
    return load_session(required=True, allowed_states={"active"})


def _json_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


@messages_bp.get("/summary")
def get_summary():
    session = _active_session()
    return jsonify(
        success=True,
        **get_message_summary(int(session["id"])),
    )


@messages_bp.get("/contacts")
def get_contacts():
    session = _active_session()
    return jsonify(
        success=True,
        contacts=list_allowed_contacts(int(session["id"])),
    )


@messages_bp.get("/conversations")
def get_conversations():
    session = _active_session()
    return jsonify(
        success=True,
        conversations=list_conversations(int(session["id"])),
    )


@messages_bp.post("/conversations")
def create_conversation():
    session = _active_session()
    payload = _json_payload()
    try:
        record = send_private_message(
            int(session["id"]),
            payload.get("recipient_id"),
            payload.get("body"),
        )
    except MessageValidationError as error:
        return jsonify(success=False, errors=error.errors), 400
    except MessagingAccessDeniedError:
        return jsonify(
            success=False,
            message="当前角色或关系不允许此私信",
        ), 403

    return jsonify(
        success=True,
        conversation=record["conversation"],
        message=record["message"],
    ), 201


@messages_bp.get("/conversations/<int:conversation_id>")
def get_conversation(conversation_id: int):
    session = _active_session()
    try:
        thread = get_conversation_messages(
            int(session["id"]),
            conversation_id,
        )
    except ConversationNotFoundError:
        return jsonify(success=False, message="会话不存在"), 404

    return jsonify(
        success=True,
        conversation=thread["conversation"],
        messages=thread["messages"],
    )


@messages_bp.post("/conversations/<int:conversation_id>/messages")
def create_message(conversation_id: int):
    session = _active_session()
    payload = _json_payload()
    try:
        record = reply_to_conversation(
            int(session["id"]),
            conversation_id,
            payload.get("body"),
        )
    except MessageValidationError as error:
        return jsonify(success=False, errors=error.errors), 400
    except MessagingAccessDeniedError:
        return jsonify(
            success=False,
            message="当前角色或关系不允许此私信",
        ), 403
    except ConversationNotFoundError:
        return jsonify(success=False, message="会话不存在"), 404

    return jsonify(
        success=True,
        conversation=record["conversation"],
        message=record["message"],
    ), 201


@messages_bp.get("/notifications")
def get_notifications():
    session = _active_session()
    return jsonify(
        success=True,
        notifications=list_notifications(int(session["id"])),
    )


@messages_bp.post("/private/<int:message_id>/read")
def read_private_message(message_id: int):
    session = _active_session()
    try:
        updated_summary = mark_private_message_read(
            int(session["id"]),
            message_id,
        )
    except MessageNotFoundError:
        return jsonify(success=False, message="消息不存在"), 404

    return jsonify(success=True, **updated_summary)


@messages_bp.post("/notifications/<int:notification_id>/read")
def read_notification(notification_id: int):
    session = _active_session()
    try:
        updated_summary = mark_notification_read(
            int(session["id"]),
            notification_id,
        )
    except MessageNotFoundError:
        return jsonify(success=False, message="消息不存在"), 404

    return jsonify(success=True, **updated_summary)


@messages_bp.post("/read-all")
def read_all_messages():
    session = _active_session()
    return jsonify(
        success=True,
        **mark_all_read(int(session["id"])),
    )


@messages_bp.post("/clear-read")
def clear_read_messages():
    session = _active_session()
    return jsonify(
        success=True,
        **clear_read_items(int(session["id"])),
    )
