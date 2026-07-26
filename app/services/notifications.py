import json

from flask import current_app

from app.extensions import db
from app.models.communication import Notification, PushSubscription


def create_notification(
    user_id,
    title,
    description,
    notification_type="request",
    action_url="",
):
    notification = Notification(
        user_id=user_id,
        title=title,
        description=description,
        type=notification_type,
        action_url=action_url,
    )
    db.session.add(notification)
    return notification


def push_is_configured():
    return bool(
        current_app.config.get("VAPID_PUBLIC_KEY")
        and current_app.config.get("VAPID_PRIVATE_KEY")
        and current_app.config.get("VAPID_SUBJECT")
    )


def _load_webpush():
    from pywebpush import WebPushException, webpush

    return webpush, WebPushException


def deliver_notification(notification):
    if not notification or not push_is_configured():
        return {"sent": 0, "failed": 0, "disabled": 0}

    try:
        webpush, web_push_exception = _load_webpush()
    except ImportError:
        current_app.logger.warning(
            "Web Push is configured but pywebpush is not installed."
        )
        return {"sent": 0, "failed": 0, "disabled": 0}

    payload = json.dumps(
        {
            "title": notification.title,
            "body": notification.description,
            "type": notification.type,
            "url": notification.action_url or "/",
            "notificationId": notification.id,
        },
        ensure_ascii=False,
    )
    subscriptions = PushSubscription.query.filter_by(
        user_id=notification.user_id,
        enabled=True,
    ).all()
    result = {"sent": 0, "failed": 0, "disabled": 0}

    for subscription in subscriptions:
        try:
            webpush(
                subscription_info=subscription.to_web_push_dict(),
                data=payload,
                vapid_private_key=current_app.config["VAPID_PRIVATE_KEY"],
                vapid_claims={"sub": current_app.config["VAPID_SUBJECT"]},
                ttl=3600,
                timeout=current_app.config["WEB_PUSH_TIMEOUT_SECONDS"],
            )
            subscription.mark_success()
            result["sent"] += 1
        except web_push_exception as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            subscription.last_error = str(exc)[:500]
            result["failed"] += 1
            if status_code in {404, 410}:
                subscription.enabled = False
                result["disabled"] += 1
        except Exception as exc:  # Push must never break the primary action.
            subscription.last_error = str(exc)[:500]
            result["failed"] += 1
            current_app.logger.exception("Unexpected Web Push delivery error")

    if subscriptions:
        db.session.commit()
    return result
