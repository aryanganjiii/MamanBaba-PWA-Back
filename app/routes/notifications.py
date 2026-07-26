from flask import Blueprint, current_app, g, request

from app.errors import ApiError
from app.extensions import db
from app.models.communication import Notification, PushSubscription
from app.services.auth import auth_required
from app.services.notifications import push_is_configured
from app.utils.http import get_json_payload, success

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.get("")
@auth_required()
def list_notifications():
    items = Notification.query.filter_by(user_id=g.current_user.id).order_by(Notification.created_at.desc()).all()
    return success({"items": [item.to_dict() for item in items]})


@bp.patch("/<int:notification_id>/read")
@auth_required()
def mark_read(notification_id):
    notification = Notification.query.filter_by(id=notification_id, user_id=g.current_user.id).first()
    if not notification:
        raise ApiError("اعلان پیدا نشد.", 404, "notification_not_found")
    notification.is_read = True
    db.session.commit()
    return success(notification.to_dict())


@bp.post("/mark-all-read")
@auth_required()
def mark_all_read():
    Notification.query.filter_by(user_id=g.current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return success({"markedAllRead": True})


@bp.get("/push/config")
@auth_required()
def push_config():
    return success(
        {
            "enabled": push_is_configured(),
            "publicKey": current_app.config["VAPID_PUBLIC_KEY"],
        }
    )


@bp.post("/push/subscriptions")
@auth_required()
def save_push_subscription():
    payload = get_json_payload()
    endpoint = str(payload.get("endpoint") or "").strip()
    keys = payload.get("keys") or {}
    p256dh = str(keys.get("p256dh") or "").strip()
    auth_key = str(keys.get("auth") or "").strip()
    if not endpoint or not p256dh or not auth_key:
        raise ApiError(
            "اطلاعات اشتراک اعلان کامل نیست.",
            422,
            "invalid_push_subscription",
        )
    if len(endpoint) > 4000 or len(p256dh) > 255 or len(auth_key) > 255:
        raise ApiError(
            "اطلاعات اشتراک اعلان معتبر نیست.",
            422,
            "invalid_push_subscription",
        )

    endpoint_hash = PushSubscription.hash_endpoint(endpoint)
    subscription = PushSubscription.query.filter_by(
        endpoint_hash=endpoint_hash
    ).first()
    if not subscription:
        subscription = PushSubscription(
            endpoint=endpoint,
            endpoint_hash=endpoint_hash,
            user_id=g.current_user.id,
            p256dh=p256dh,
            auth=auth_key,
        )
        db.session.add(subscription)

    subscription.user_id = g.current_user.id
    subscription.endpoint = endpoint
    subscription.p256dh = p256dh
    subscription.auth = auth_key
    subscription.user_agent = request.headers.get("User-Agent", "")[:500]
    subscription.enabled = True
    subscription.last_error = ""
    db.session.commit()
    return success({"subscribed": True}, status=201)


@bp.delete("/push/subscriptions")
@auth_required()
def delete_push_subscription():
    payload = get_json_payload()
    endpoint = str(payload.get("endpoint") or "").strip()
    if endpoint:
        PushSubscription.query.filter_by(
            endpoint_hash=PushSubscription.hash_endpoint(endpoint),
            user_id=g.current_user.id,
        ).delete()
        db.session.commit()
    return success({"subscribed": False})
