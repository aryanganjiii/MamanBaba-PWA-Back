from flask import Blueprint, g

from app.errors import ApiError
from app.extensions import db
from app.models.communication import Notification
from app.services.auth import auth_required
from app.utils.http import success

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
