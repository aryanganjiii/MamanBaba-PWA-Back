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


def push_runtime_status():
    configured = push_is_configured()
    try:
        _load_webpush()
        runtime_available = True
    except ImportError:
        runtime_available = False
    return {
        "configured": configured,
        "runtimeAvailable": runtime_available,
        "enabled": configured and runtime_available,
    }


def deliver_notification(notification):
    result = {
        "subscriptions": 0,
        "sent": 0,
        "failed": 0,
        "removed": 0,
        "errors": [],
    }
    if not notification:
        return result
    if not push_is_configured():
        current_app.logger.warning(
            "Web Push delivery skipped because VAPID is not fully configured."
        )
        return result

    try:
        webpush, web_push_exception = _load_webpush()
    except ImportError:
        current_app.logger.warning(
            "Web Push is configured but pywebpush is not installed."
        )
        result["errors"].append(
            {
                "code": "push_runtime_unavailable",
                "message": "pywebpush is not installed.",
            }
        )
        return result

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
    result["subscriptions"] = len(subscriptions)
    if not subscriptions:
        current_app.logger.info(
            "Web Push delivery skipped for user %s: no active subscription.",
            notification.user_id,
        )
        return result

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
            error_message = str(exc)[:500]
            subscription.last_error = error_message
            result["failed"] += 1
            result["errors"].append(
                {
                    "code": "push_provider_error",
                    "status": status_code,
                    "message": error_message,
                }
            )
            current_app.logger.warning(
                "Web Push provider rejected subscription %s with status %s: %s",
                subscription.id,
                status_code,
                error_message,
            )
            if status_code in {404, 410}:
                db.session.delete(subscription)
                result["removed"] += 1
        except Exception as exc:  # Push must never break the primary action.
            error_message = str(exc)[:500]
            subscription.last_error = error_message
            result["failed"] += 1
            result["errors"].append(
                {
                    "code": "push_delivery_error",
                    "message": error_message,
                }
            )
            current_app.logger.exception("Unexpected Web Push delivery error")

    if subscriptions:
        db.session.commit()
    return result
