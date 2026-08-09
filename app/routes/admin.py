import secrets
from datetime import date

from flask import Blueprint, current_app, g, request
from sqlalchemy import func, or_

from app.errors import ApiError
from app.extensions import db
from app.models.caregiver import CaregiverApplication, CaregiverApplicationChange
from app.models.user import User
from app.services.auth import admin_required, create_admin_access_token
from app.services.caregiver_accounts import review_caregiver_application
from app.services.caregiver_profile_updates import review_caregiver_application_change
from app.utils.http import get_json_payload, paginate_query, pagination_params, success

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _application_or_404(application_id):
    application = db.session.get(CaregiverApplication, application_id)
    if not application:
        raise ApiError(
            "درخواست همکاری پیدا نشد.",
            404,
            "application_not_found",
        )
    return application


def _application_list_item(application):
    pending_changes = sum(
        1 for change in application.profile_changes if change.status == "pending"
    )
    return {
        "id": application.id,
        "fullName": application.full_name,
        "phone": application.user.phone if application.user else "",
        "city": application.city,
        "province": application.province,
        "experienceLevel": application.experience_level,
        "hourlyRate": application.hourly_rate,
        "status": application.status,
        "fileCount": len(application.files),
        "pendingChangeCount": pending_changes,
        "hasPendingChanges": pending_changes > 0,
        "profileImageUrl": application.profile_image_url,
        "reviewedAt": application._iso(application.reviewed_at),
        "createdAt": application._iso(application.created_at),
    }


@bp.post("/auth/login")
def admin_login():
    payload = get_json_payload()
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    expected_username = current_app.config["ADMIN_USERNAME"]
    expected_password = current_app.config["ADMIN_PASSWORD"]

    if not expected_password:
        raise ApiError(
            "رمز عبور مدیریت روی سرور تنظیم نشده است.",
            503,
            "admin_credentials_not_configured",
        )

    username_matches = secrets.compare_digest(username, expected_username)
    password_matches = secrets.compare_digest(password, expected_password)
    if not username_matches or not password_matches:
        raise ApiError(
            "نام کاربری یا رمز عبور صحیح نیست.",
            401,
            "invalid_admin_credentials",
        )

    token = create_admin_access_token(expected_username)
    return success(
        {
            "accessToken": token,
            "tokenType": "Bearer",
            "admin": {
                "username": expected_username,
                "roles": ["admin"],
            },
        }
    )


@bp.get("/auth/me")
@admin_required
def admin_me():
    return success(g.current_admin)


@bp.get("/caregiver-applications/summary")
@admin_required
def caregiver_application_summary():
    status_rows = (
        db.session.query(
            CaregiverApplication.status,
            func.count(CaregiverApplication.id),
        )
        .group_by(CaregiverApplication.status)
        .all()
    )
    counts = {status: count for status, count in status_rows}
    submitted_today = (
        CaregiverApplication.query.filter(
            func.date(CaregiverApplication.created_at) == date.today().isoformat()
        ).count()
    )
    reviewed_today = (
        CaregiverApplication.query.filter(
            CaregiverApplication.reviewed_at.isnot(None),
            func.date(CaregiverApplication.reviewed_at) == date.today().isoformat(),
        ).count()
    )
    pending_profile_updates = CaregiverApplicationChange.query.filter_by(
        status="pending"
    ).count()
    return success(
        {
            "total": sum(counts.values()),
            "pendingReview": counts.get("pending_review", 0),
            "approved": counts.get("approved", 0),
            "rejected": counts.get("rejected", 0),
            "submittedToday": submitted_today,
            "reviewedToday": reviewed_today,
            "pendingProfileUpdates": pending_profile_updates,
        }
    )


@bp.get("/caregiver-applications")
@admin_required
def list_caregiver_applications():
    page, per_page = pagination_params(default_per_page=15, max_per_page=50)
    status = str(request.args.get("status") or "").strip().lower()
    search = str(request.args.get("search") or "").strip()
    city = str(request.args.get("city") or "").strip()
    sort = str(request.args.get("sort") or "newest").strip().lower()

    query = CaregiverApplication.query.join(User)
    if status and status != "all":
        if status not in {"pending_review", "approved", "rejected"}:
            raise ApiError(
                "فیلتر وضعیت معتبر نیست.",
                422,
                "invalid_application_status_filter",
            )
        query = query.filter(CaregiverApplication.status == status)
    if city:
        query = query.filter(CaregiverApplication.city == city)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                CaregiverApplication.full_name.ilike(pattern),
                CaregiverApplication.national_code.ilike(pattern),
                User.phone.ilike(pattern),
            )
        )

    if sort == "oldest":
        query = query.order_by(CaregiverApplication.created_at.asc())
    elif sort == "name":
        query = query.order_by(CaregiverApplication.full_name.asc())
    else:
        query = query.order_by(CaregiverApplication.created_at.desc())

    items, meta = paginate_query(query, page, per_page)
    cities = [
        row[0]
        for row in db.session.query(CaregiverApplication.city)
        .filter(CaregiverApplication.city != "")
        .distinct()
        .order_by(CaregiverApplication.city.asc())
        .all()
    ]
    return success(
        {
            "items": [_application_list_item(item) for item in items],
            "cities": cities,
        },
        meta=meta,
    )


@bp.get("/caregiver-applications/<int:application_id>")
@admin_required
def caregiver_application_detail(application_id):
    return success(_application_or_404(application_id).to_admin_dict())


@bp.patch("/caregiver-applications/<int:application_id>/status")
@admin_required
def update_caregiver_application_status(application_id):
    payload = get_json_payload()
    status = str(payload.get("status") or "").strip().lower()
    note = str(payload.get("note") or "").strip()
    if status not in {"approved", "rejected"}:
        raise ApiError(
            "تصمیم بررسی معتبر نیست.",
            422,
            "invalid_review_decision",
            {"allowed": ["approved", "rejected"]},
        )
    if status == "rejected" and not note:
        raise ApiError(
            "برای رد درخواست، ثبت دلیل الزامی است.",
            422,
            "rejection_note_required",
        )

    application, profile = review_caregiver_application(
        application_id,
        status,
        review_note=note,
        reviewed_by=g.current_admin["username"],
    )
    return success(
        {
            "application": application.to_admin_dict(),
            "caregiver": profile.to_detail_dict() if profile else None,
        },
        message=(
            "درخواست مراقب تأیید شد."
            if status == "approved"
            else "درخواست مراقب رد شد."
        ),
    )


@bp.patch("/caregiver-applications/<int:application_id>/updates/<int:change_id>/status")
@admin_required
def update_caregiver_profile_change_status(application_id, change_id):
    payload = get_json_payload()
    status = str(payload.get("status") or "").strip().lower()
    note = str(payload.get("note") or "").strip()
    if status not in {"approved", "rejected"}:
        raise ApiError(
            "Invalid profile update decision.",
            422,
            "invalid_review_decision",
            {"allowed": ["approved", "rejected"]},
        )
    if status == "rejected" and not note:
        raise ApiError(
            "A rejection note is required.",
            422,
            "rejection_note_required",
        )
    application, profile = review_caregiver_application_change(
        application_id,
        change_id,
        status,
        review_note=note,
        reviewed_by=g.current_admin["username"],
    )
    return success(
        {
            "application": application.to_admin_dict(),
            "caregiver": profile.to_detail_dict() if profile else None,
        }
    )
