from flask import Blueprint, g, request

from app.errors import ApiError
from app.extensions import db
from app.models.communication import Conversation, Message
from app.services.auth import role_required
from app.services.notifications import create_notification, deliver_notification
from app.utils.http import get_json_payload, success

bp = Blueprint("conversations", __name__, url_prefix="/conversations")


def _owned_conversation(conversation_id):
    conversation = Conversation.query.filter_by(id=conversation_id, family_user_id=g.current_user.id).first()
    if not conversation:
        raise ApiError("گفتگو پیدا نشد.", 404, "conversation_not_found")
    return conversation


@bp.get("")
@role_required("family")
def list_conversations():
    filter_name = request.args.get("filter", "all")
    search = request.args.get("q", "").strip()
    query = Conversation.query.filter_by(family_user_id=g.current_user.id)
    if filter_name == "unread":
        query = query.filter(Conversation.unread_for_family > 0)
    elif filter_name == "support":
        query = query.filter_by(type="support")
    conversations = query.order_by(Conversation.updated_at.desc()).all()
    if search:
        conversations = [
            item
            for item in conversations
            if search in item.to_dict()["name"]
            or search in item.to_dict()["role"]
            or search in item.to_dict()["message"]
        ]
    return success({"items": [item.to_dict() for item in conversations]})


@bp.get("/<int:conversation_id>/messages")
@role_required("family")
def list_messages(conversation_id):
    conversation = _owned_conversation(conversation_id)
    conversation.unread_for_family = 0
    db.session.commit()
    return success({"conversation": conversation.to_dict(), "items": [message.to_dict() for message in conversation.messages]})


@bp.post("/<int:conversation_id>/messages")
@role_required("family")
def send_message(conversation_id):
    conversation = _owned_conversation(conversation_id)
    payload = get_json_payload()
    body = (payload.get("text") or payload.get("message") or "").strip()
    if not body:
        raise ApiError("متن پیام الزامی است.", 422, "missing_message")
    message = Message(
        conversation_id=conversation.id,
        sender_user_id=g.current_user.id,
        sender_type="family",
        body=body,
        time_label="الان",
    )
    db.session.add(message)
    notification = None
    if conversation.caregiver and conversation.caregiver.user_id:
        notification = create_notification(
            conversation.caregiver.user_id,
            "پیام جدید از خانواده",
            body[:180],
            "message",
            "/?view=caregiver-dashboard&tab=messages",
        )
    db.session.commit()
    deliver_notification(notification)
    return success(message.to_dict(), status=201)


@bp.post("/support")
@role_required("family")
def create_support_conversation():
    conversation = Conversation.query.filter_by(family_user_id=g.current_user.id, type="support").first()
    if not conversation:
        conversation = Conversation(
            family_user_id=g.current_user.id,
            type="support",
            title="پشتیبانی مامان بابا",
            role_label="پشتیبانی",
            online=True,
        )
        db.session.add(conversation)
        db.session.flush()
        db.session.add(
            Message(
                conversation_id=conversation.id,
                sender_type="support",
                body="سلام، چطور می‌توانیم کمک کنیم؟",
                time_label="الان",
            )
        )
        db.session.commit()
    return success(conversation.to_dict(), status=201)
