from flask import Blueprint, g

from app.errors import ApiError
from app.extensions import db
from app.models.care_request import CareRequest
from app.models.caregiver import FavoriteCaregiver
from app.models.communication import Notification
from app.models.user import Address
from app.services.auth import auth_required
from app.services.catalog_data import SERVICE_SUGGESTIONS
from app.utils.http import get_json_payload, success

bp = Blueprint("family", __name__, url_prefix="/family")


def _apply_user_profile(user, payload):
    if "fullName" in payload or "full_name" in payload:
        user.full_name = payload.get("fullName", payload.get("full_name", user.full_name))
    if "firstName" in payload or "first_name" in payload:
        user.first_name = payload.get("firstName", payload.get("first_name", user.first_name))
    if "city" in payload:
        user.city = payload["city"]
    if "neighborhood" in payload:
        user.neighborhood = payload["neighborhood"]
    if "avatar" in payload or "avatarUrl" in payload:
        user.avatar_url = payload.get("avatar", payload.get("avatarUrl", user.avatar_url))


@bp.get("/profile")
@auth_required()
def profile():
    return success(g.current_user.to_dict(include_stats=True))


@bp.patch("/profile")
@auth_required()
def update_profile():
    payload = get_json_payload()
    _apply_user_profile(g.current_user, payload)
    db.session.commit()
    return success(g.current_user.to_dict(include_stats=True), message="پروفایل به‌روزرسانی شد.")


@bp.get("/home")
@auth_required()
def home():
    user = g.current_user
    active_request = (
        CareRequest.query.filter(
            CareRequest.user_id == user.id,
            CareRequest.status.in_(["active", "pending"]),
        )
        .order_by(CareRequest.created_at.desc())
        .first()
    )
    unread_notifications = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return success(
        {
            "user": user.to_dict(include_stats=True),
            "activeRequest": active_request.to_card_dict() if active_request else None,
            "notificationCount": unread_notifications,
            "serviceSuggestions": SERVICE_SUGGESTIONS,
        }
    )


@bp.get("/addresses")
@auth_required()
def addresses():
    return success({"items": [address.to_dict() for address in g.current_user.addresses]})


@bp.post("/addresses")
@auth_required()
def create_address():
    payload = get_json_payload()
    for field in ["province", "city"]:
        if not payload.get(field):
            raise ApiError("استان و شهر برای ثبت آدرس الزامی است.", 422, "missing_address_fields")
    address = Address(
        user_id=g.current_user.id,
        label=payload.get("label", "خانه"),
        province=payload["province"],
        city=payload["city"],
        neighborhood=payload.get("neighborhood", ""),
        address_line=payload.get("addressLine", payload.get("address_line", "")),
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        is_default=bool(payload.get("isDefault", payload.get("is_default", False))),
    )
    if address.is_default:
        Address.query.filter_by(user_id=g.current_user.id).update({"is_default": False})
    db.session.add(address)
    db.session.commit()
    return success(address.to_dict(), status=201)


@bp.patch("/addresses/<int:address_id>")
@auth_required()
def update_address(address_id):
    address = Address.query.filter_by(id=address_id, user_id=g.current_user.id).first()
    if not address:
        raise ApiError("آدرس پیدا نشد.", 404, "address_not_found")
    payload = get_json_payload()
    for attr, key in [
        ("label", "label"),
        ("province", "province"),
        ("city", "city"),
        ("neighborhood", "neighborhood"),
        ("address_line", "addressLine"),
        ("latitude", "latitude"),
        ("longitude", "longitude"),
    ]:
        if key in payload:
            setattr(address, attr, payload[key])
    if "isDefault" in payload:
        if payload["isDefault"]:
            Address.query.filter_by(user_id=g.current_user.id).update({"is_default": False})
        address.is_default = bool(payload["isDefault"])
    db.session.commit()
    return success(address.to_dict())


@bp.delete("/addresses/<int:address_id>")
@auth_required()
def delete_address(address_id):
    address = Address.query.filter_by(id=address_id, user_id=g.current_user.id).first()
    if not address:
        raise ApiError("آدرس پیدا نشد.", 404, "address_not_found")
    db.session.delete(address)
    db.session.commit()
    return success({"deleted": True})


@bp.get("/favorites")
@auth_required()
def favorites():
    favorites_query = FavoriteCaregiver.query.filter_by(user_id=g.current_user.id).all()
    return success({"items": [favorite.caregiver.to_family_card_dict(favorite=True) for favorite in favorites_query]})
