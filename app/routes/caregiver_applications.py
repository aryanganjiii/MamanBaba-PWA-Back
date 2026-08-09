import re

from flask import Blueprint, g, request

from app.errors import ApiError
from app.extensions import db
from app.models.caregiver import CaregiverApplication, CaregiverApplicationFile, CaregiverApplicationItem
from app.services.auth import role_required
from app.services.caregiver_accounts import review_caregiver_application
from app.services.catalog_data import CAREGIVER_REGISTRATION_OPTIONS
from app.services.caregiver_profile_updates import (
    update_caregiver_application,
)
from app.services.files import save_upload
from app.services.notifications import create_notification, deliver_notification
from app.utils.http import success
from app.utils.validation import as_list, bool_value, normalize_digits, require_fields

bp = Blueprint("caregiver_applications", __name__, url_prefix="/caregiver-applications")


def _payload():
    return request.get_json(silent=True) if request.is_json else request.form


def _field(payload, camel, snake=None, default=None):
    snake = snake or camel
    return payload.get(camel, payload.get(snake, default))


def _list_field(payload, camel, snake=None):
    if request.is_json:
        return as_list(_field(payload, camel, snake, []))
    values = request.form.getlist(camel) or request.form.getlist(snake or camel)
    if values:
        result = []
        for value in values:
            result.extend(as_list(value))
        return result
    return as_list(_field(payload, camel, snake, []))


def _money(value):
    normalized = normalize_digits(value)
    digits = re.sub(r"\D", "", normalized)
    return int(digits or 0)


@bp.get("/options")
def options():
    return success(CAREGIVER_REGISTRATION_OPTIONS)


@bp.post("")
@role_required("caregiver")
def create_application():
    payload = _payload() or {}
    existing = (
        CaregiverApplication.query.filter_by(user_id=g.current_user.id)
        .filter(CaregiverApplication.status.in_(["draft", "pending_review", "approved"]))
        .order_by(CaregiverApplication.created_at.desc())
        .first()
    )
    if existing:
        raise ApiError(
            "برای این حساب قبلاً درخواست مراقب ثبت شده است.",
            409,
            "caregiver_application_exists",
            {"applicationId": existing.id, "status": existing.status},
        )

    normalized = {
        "fullName": _field(payload, "fullName", "full_name"),
        "nationalCode": _field(payload, "nationalCode", "national_code"),
        "birthDate": _field(payload, "birthDate", "birth_date"),
        "gender": _field(payload, "gender"),
        "maritalStatus": _field(payload, "maritalStatus", "marital_status"),
        "province": _field(payload, "province"),
        "city": _field(payload, "city"),
        "experienceLevel": _field(payload, "experienceLevel", "experience_level"),
        "startTime": _field(payload, "startTime", "start_time", "08:00"),
        "endTime": _field(payload, "endTime", "end_time", "16:00"),
        "hourlyRate": _money(_field(payload, "hourlyRate", "hourly_rate", 0)),
        "expectationNotes": _field(payload, "expectationNotes", "expectation_notes", ""),
        "aboutMe": _field(payload, "aboutMe", "about_me"),
        "profileImageReminderSkipped": bool_value(
            _field(payload, "profileImageReminderSkipped", "profile_image_reminder_skipped", False)
        ),
        "acceptedTerms": bool_value(_field(payload, "acceptedTerms", "accepted_terms", False)),
        "canStayOvernight": bool_value(_field(payload, "canStayOvernight", "can_stay_overnight", False)),
        "availableOnHolidays": bool_value(_field(payload, "availableOnHolidays", "available_on_holidays", False)),
    }
    require_fields(
        normalized,
        [
            "fullName",
            "nationalCode",
            "birthDate",
            "gender",
            "maritalStatus",
            "province",
            "city",
            "experienceLevel",
            "hourlyRate",
            "aboutMe",
        ],
    )
    if not normalized["acceptedTerms"]:
        raise ApiError("برای ثبت نهایی، قوانین و شرایط باید تایید شود.", 422, "terms_not_accepted")

    profile_image = request.files.get("profileImage") if not request.is_json else None
    profile_saved = save_upload(profile_image, "profile-images") if profile_image else None

    application = CaregiverApplication(
        user_id=g.current_user.id,
        full_name=normalized["fullName"],
        national_code=normalize_digits(normalized["nationalCode"]),
        birth_date=normalized["birthDate"],
        gender=normalized["gender"],
        marital_status=normalized["maritalStatus"],
        province=normalized["province"],
        city=normalized["city"],
        experience_level=normalized["experienceLevel"],
        start_time=normalized["startTime"],
        end_time=normalized["endTime"],
        can_stay_overnight=normalized["canStayOvernight"],
        available_on_holidays=normalized["availableOnHolidays"],
        hourly_rate=normalized["hourlyRate"],
        expectation_notes=normalized["expectationNotes"],
        about_me=normalized["aboutMe"],
        profile_image_url=profile_saved["url"] if profile_saved else _field(payload, "profileImageUrl", "profile_image_url", ""),
        profile_image_reminder_skipped=normalized["profileImageReminderSkipped"],
        accepted_terms=normalized["acceptedTerms"],
        status="pending_review",
    )
    db.session.add(application)
    db.session.flush()

    item_map = {
        "skills": _list_field(payload, "skills"),
        "certificates": _list_field(payload, "certificates"),
        "service_types": _list_field(payload, "serviceTypes", "service_types"),
        "collaboration_types": _list_field(payload, "collaborationTypes", "collaboration_types"),
        "available_days": _list_field(payload, "availableDays", "available_days"),
        "service_areas": _list_field(payload, "serviceAreas", "service_areas"),
    }
    required_lists = ["skills", "service_types", "collaboration_types", "available_days", "service_areas"]
    missing_lists = [key for key in required_lists if not item_map[key]]
    if missing_lists:
        raise ApiError("برخی گزینه‌های ضروری ثبت‌نام انتخاب نشده‌اند.", 422, "missing_registration_items", {"items": missing_lists})

    for category, values in item_map.items():
        for value in values:
            db.session.add(CaregiverApplicationItem(application_id=application.id, category=category, value=value))

    for file_storage in request.files.getlist("certificateFiles"):
        saved = save_upload(file_storage, "certificates")
        if saved:
            db.session.add(
                CaregiverApplicationFile(
                    application_id=application.id,
                    file_type="certificate",
                    original_name=saved["original_name"],
                    stored_name=saved["stored_name"],
                    url=saved["url"],
                )
            )

    notification = create_notification(
        g.current_user.id,
        "درخواست ثبت‌نام مراقب دریافت شد",
        "اطلاعات شما ثبت شد و پس از بررسی کارشناسان، نتیجه برایتان ارسال می‌شود.",
        "caregiver_application",
        "/?view=caregiver-status",
    )
    db.session.commit()
    deliver_notification(notification)
    return success(application.to_dict(), status=201, message="درخواست همکاری شما ثبت شد.")


@bp.get("/me")
@role_required("caregiver")
def my_application():
    application = (
        CaregiverApplication.query.filter_by(user_id=g.current_user.id)
        .order_by(CaregiverApplication.created_at.desc())
        .first()
    )
    return success(application.to_dict() if application else None)


@bp.patch("/me")
@role_required("caregiver")
def update_my_application():
    payload = request.get_json(silent=True) if request.is_json else request.form
    application = (
        CaregiverApplication.query.filter_by(user_id=g.current_user.id)
        .order_by(CaregiverApplication.created_at.desc())
        .first()
    )
    if not application:
        raise ApiError(
            "Ø¯Ø±Ø®ÙˆØ§Ø³Øª Ù‡Ù…Ú©Ø§Ø±ÛŒ Ù¾ÛŒØ¯Ø§ Ù†Ø´Ø¯.",
            404,
            "caregiver_application_not_found",
        )
    try:
        updated = update_caregiver_application(
            application,
            payload or {},
            request.files.getlist("certificateFiles"),
        )
    except Exception:
        db.session.rollback()
        raise
    return success(updated.to_dict())


@bp.get("/<int:application_id>")
@role_required("caregiver", "admin")
def application_detail(application_id):
    application = db.session.get(CaregiverApplication, application_id)
    if not application:
        raise ApiError("درخواست همکاری پیدا نشد.", 404, "application_not_found")
    if application.user_id != g.current_user.id and not g.current_user.has_role("admin"):
        raise ApiError("اجازه مشاهده این درخواست را ندارید.", 403, "application_forbidden")
    return success(application.to_dict())


@bp.patch("/<int:application_id>/status")
@role_required("admin")
def update_application_status(application_id):
    payload = request.get_json(silent=True) or {}
    application, profile = review_caregiver_application(
        application_id,
        str(payload.get("status") or "").strip().lower(),
    )
    return success(
        {
            "application": application.to_dict(),
            "caregiver": profile.to_detail_dict() if profile else None,
        }
    )
