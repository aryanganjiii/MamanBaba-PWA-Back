import re

from app.errors import ApiError
from app.extensions import db
from app.models.caregiver import (
    CaregiverApplication,
    CaregiverApplicationReview,
    CaregiverAvailableDay,
    CaregiverCertificate,
    CaregiverCollaborationType,
    CaregiverProfile,
    CaregiverServiceArea,
    CaregiverServiceType,
    CaregiverSkill,
)
from app.models.base import utc_now
from app.utils.validation import normalize_digits


def _experience_years(label):
    numbers = re.findall(r"\d+", normalize_digits(label or ""))
    return int(numbers[-1]) if numbers else 0


def _unique_slug(user_id):
    base = f"caregiver-{user_id}"
    slug = base
    suffix = 2
    while CaregiverProfile.query.filter_by(slug=slug).first():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def approve_caregiver_application(application, commit=True):
    if not application.user_id or not application.user:
        raise ApiError(
            "درخواست قدیمی به حساب کاربری متصل نیست و باید ابتدا تعیین مالک شود.",
            409,
            "caregiver_application_has_no_user",
        )

    profile = CaregiverProfile.query.filter_by(user_id=application.user_id).first()
    if not profile:
        profile = CaregiverProfile(
            user_id=application.user_id,
            slug=_unique_slug(application.user_id),
            full_name=application.full_name,
        )
        db.session.add(profile)

    profile.full_name = application.full_name
    profile.national_code = application.national_code
    profile.birth_date = application.birth_date
    profile.gender = application.gender
    profile.marital_status = application.marital_status
    profile.province = application.province
    profile.city = application.city
    profile.experience_level = application.experience_level
    profile.experience_years = _experience_years(application.experience_level)
    profile.hourly_rate = application.hourly_rate
    profile.bio = application.about_me
    profile.image_url = application.profile_image_url
    profile.start_time = application.start_time
    profile.end_time = application.end_time
    profile.can_stay_overnight = application.can_stay_overnight
    profile.available_on_holidays = application.available_on_holidays
    profile.expectation_notes = application.expectation_notes
    profile.verified = True
    profile.public_status = "public"

    application.user.full_name = application.full_name
    application.user.city = application.city
    application.user.add_role("caregiver")

    relationship_models = {
        "skills": CaregiverSkill,
        "certificates": CaregiverCertificate,
        "service_types": CaregiverServiceType,
        "collaboration_types": CaregiverCollaborationType,
        "available_days": CaregiverAvailableDay,
        "service_areas": CaregiverServiceArea,
    }
    grouped = {key: [] for key in relationship_models}
    for item in application.items:
        if item.category in grouped:
            grouped[item.category].append(item.value)
    grouped["certificates"].extend(file.original_name for file in application.files)

    db.session.flush()
    for relationship_name, model in relationship_models.items():
        getattr(profile, relationship_name).clear()
        for value in dict.fromkeys(grouped[relationship_name]):
            db.session.add(model(caregiver_id=profile.id, value=value))

    application.status = "approved"
    if commit:
        db.session.commit()
    return profile


def review_caregiver_application(
    application_id,
    status,
    review_note="",
    reviewed_by="system",
):
    application = db.session.get(CaregiverApplication, application_id)
    if not application:
        raise ApiError("درخواست همکاری پیدا نشد.", 404, "application_not_found")
    previous_status = application.status
    review_note = str(review_note or "").strip()
    reviewed_by = str(reviewed_by or "system").strip()
    if status == "approved":
        profile = approve_caregiver_application(application, commit=False)
    else:
        profile = None
    if status not in {"rejected", "pending_review"}:
        if status != "approved":
            raise ApiError(
                "وضعیت بررسی معتبر نیست.",
                422,
                "invalid_application_status",
                {"allowed": ["approved", "rejected", "pending_review"]},
            )
    if status != "approved":
        application.status = status
        profile = CaregiverProfile.query.filter_by(
            user_id=application.user_id
        ).first()
        if profile:
            profile.public_status = status
            profile.verified = False
    application.reviewed_at = utc_now()
    application.review_note = review_note
    application.reviewed_by = reviewed_by
    db.session.add(
        CaregiverApplicationReview(
            application_id=application.id,
            previous_status=previous_status,
            status=status,
            note=review_note,
            reviewed_by=reviewed_by,
        )
    )
    db.session.commit()
    return application, profile
