import os
import re

from app.errors import ApiError
from app.extensions import db
from app.models.caregiver import (
    CaregiverApplication,
    CaregiverApplicationChange,
    CaregiverApplicationFile,
    CaregiverApplicationItem,
    CaregiverAvailableDay,
    CaregiverCertificate,
    CaregiverProfile,
    CaregiverServiceArea,
    CaregiverSkill,
)
from app.services.catalog_data import CAREGIVER_REGISTRATION_OPTIONS
from app.services.files import save_upload
from app.services.notifications import create_notification, deliver_notification
from app.models.base import utc_now
from app.utils.validation import as_list, bool_value, normalize_digits


IMMUTABLE_FIELDS = {
    "id",
    "userId",
    "user_id",
    "phone",
    "mobile",
    "mobileNumber",
    "mobile_number",
    "fullName",
    "full_name",
    "nationalCode",
    "national_code",
    "birthDate",
    "birth_date",
    "gender",
    "maritalStatus",
    "marital_status",
    "province",
    "city",
}

FIELD_ALIASES = {
    "availableDays": ("availableDays", "available_days"),
    "startTime": ("startTime", "start_time"),
    "endTime": ("endTime", "end_time"),
    "canStayOvernight": ("canStayOvernight", "can_stay_overnight"),
    "availableOnHolidays": ("availableOnHolidays", "available_on_holidays"),
    "serviceAreas": ("serviceAreas", "service_areas"),
    "experienceLevel": ("experienceLevel", "experience_level"),
    "skills": ("skills",),
    "certificates": ("certificates",),
}

ALLOWED_FILE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_CERTIFICATE_FILE_SIZE = 5 * 1024 * 1024

PROFILE_RELATIONSHIPS = {
    "skills": CaregiverSkill,
    "certificates": CaregiverCertificate,
    "availableDays": CaregiverAvailableDay,
    "serviceAreas": CaregiverServiceArea,
}

PROFILE_RELATIONSHIP_ATTRIBUTES = {
    "skills": "skills",
    "certificates": "certificates",
    "availableDays": "available_days",
    "serviceAreas": "service_areas",
}


def _keys(payload):
    return set(payload.keys()) if payload is not None else set()


def _has(payload, aliases):
    keys = _keys(payload)
    return any(alias in keys for alias in aliases)


def _raw_values(payload, aliases):
    if payload is None:
        return []
    for alias in aliases:
        if alias not in _keys(payload):
            continue
        if hasattr(payload, "getlist"):
            return payload.getlist(alias)
        return payload.get(alias)
    return []


def _list_value(payload, aliases):
    raw = _raw_values(payload, aliases)
    if isinstance(raw, list):
        values = []
        for item in raw:
            values.extend(as_list(item))
        return _clean_values(values)
    return _clean_values(as_list(raw))


def _scalar_value(payload, aliases, default=None):
    raw = _raw_values(payload, aliases)
    if isinstance(raw, list):
        return raw[-1] if raw else default
    return raw if raw is not None else default


def _clean_values(values):
    result = []
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _application_for_user(user_id):
    application = (
        CaregiverApplication.query.filter_by(user_id=user_id)
        .order_by(CaregiverApplication.created_at.desc())
        .first()
    )
    if not application:
        raise ApiError(
            "Caregiver application was not found.",
            404,
            "caregiver_application_not_found",
        )
    return application


def _raise_immutable(field):
    raise ApiError(
        "Verified identity information cannot be changed.",
        422,
        "immutable_field",
        {"field": field},
    )


def _validate_payload_keys(payload):
    for field in _keys(payload):
        if field in IMMUTABLE_FIELDS:
            _raise_immutable(field)

    allowed = {
        alias
        for aliases in FIELD_ALIASES.values()
        for alias in aliases
    }
    allowed.add("certificateFiles")
    unsupported = sorted(field for field in _keys(payload) if field not in allowed)
    if unsupported:
        raise ApiError(
            "The submitted field is not editable.",
            422,
            "unsupported_field",
            {"fields": unsupported},
        )


def _validate_time(value, field):
    normalized = normalize_digits(value)
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", normalized):
        raise ApiError(
            "Time must use the HH:MM format.",
            422,
            "invalid_time",
            {"field": field},
        )
    return normalized


def _validate_catalog_values(values, allowed, field):
    invalid = [value for value in values if value not in allowed]
    if invalid:
        raise ApiError(
            "One or more selected values are not valid.",
            422,
            "invalid_catalog_value",
            {"field": field, "invalid": invalid},
        )


def _replace_application_items(application, category, values):
    for item in list(application.items):
        if item.category == category:
            db.session.delete(item)
    for value in values:
        db.session.add(
            CaregiverApplicationItem(
                application_id=application.id,
                category=category,
                value=value,
            )
        )


def _replace_profile_relationship(profile, relationship_name, values):
    relationship = getattr(profile, PROFILE_RELATIONSHIP_ATTRIBUTES[relationship_name])
    for item in list(relationship):
        db.session.delete(item)
    model = PROFILE_RELATIONSHIPS[relationship_name]
    db.session.flush()
    for value in values:
        db.session.add(model(caregiver_id=profile.id, value=value))


def _active_change(application):
    return next(
        (change for change in application.profile_changes if change.status == "pending"),
        None,
    )


def _merge_pending_change(application, changes):
    change = _active_change(application)
    if not change:
        change = CaregiverApplicationChange(
            application_id=application.id,
            change_type="profile_update",
        )
        db.session.add(change)
        db.session.flush()

    merged = dict(change.payload)
    for key, value in changes.items():
        if key in {"certificates", "fileIds"}:
            merged[key] = _clean_values(merged.get(key, []) + value) if key == "certificates" else list(
                dict.fromkeys([*merged.get(key, []), *value])
            )
        else:
            merged[key] = value
    change.payload = merged
    return change


def _validate_uploads(file_storages):
    for file_storage in file_storages:
        if not file_storage or not file_storage.filename:
            continue
        extension = os.path.splitext(file_storage.filename)[1].lower()
        if extension not in ALLOWED_FILE_EXTENSIONS:
            raise ApiError(
                "Only JPG, JPEG, PNG and PDF files are allowed.",
                422,
                "invalid_file_type",
                {"file": file_storage.filename},
            )
        stream = file_storage.stream
        try:
            current_position = stream.tell()
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(current_position)
        except (AttributeError, OSError):
            raise ApiError(
                "The uploaded file could not be read.",
                422,
                "invalid_file",
                {"file": file_storage.filename},
            )
        if size > MAX_CERTIFICATE_FILE_SIZE:
            raise ApiError(
                "Each certificate file must be 5 MB or smaller.",
                422,
                "file_too_large",
                {"file": file_storage.filename, "maxBytes": MAX_CERTIFICATE_FILE_SIZE},
            )


def _save_certificate_files(application, file_storages):
    file_ids = []
    for file_storage in file_storages:
        if not file_storage or not file_storage.filename:
            continue
        saved = save_upload(file_storage, "certificates")
        if not saved:
            continue
        file_record = CaregiverApplicationFile(
            application_id=application.id,
            file_type="certificate",
            original_name=saved["original_name"],
            stored_name=saved["stored_name"],
            url=saved["url"],
            review_status="pending",
        )
        db.session.add(file_record)
        db.session.flush()
        file_ids.append(file_record.id)
    return file_ids


def _apply_operational_to_profile(profile, values):
    if not profile:
        return
    for field in ("startTime", "endTime", "canStayOvernight", "availableOnHolidays"):
        if field in values:
            setattr(
                profile,
                {
                    "startTime": "start_time",
                    "endTime": "end_time",
                    "canStayOvernight": "can_stay_overnight",
                    "availableOnHolidays": "available_on_holidays",
                }[field],
                values[field],
            )
    if "availableDays" in values:
        _replace_profile_relationship(profile, "availableDays", values["availableDays"])
    if "serviceAreas" in values:
        _replace_profile_relationship(profile, "serviceAreas", values["serviceAreas"])


def update_caregiver_application(application, payload, file_storages):
    _validate_payload_keys(payload)
    if not _keys(payload) and not any(file_storages):
        raise ApiError("At least one editable field is required.", 422, "no_changes_submitted")

    grouped = application.grouped_items()
    options = CAREGIVER_REGISTRATION_OPTIONS
    operational = {}

    if _has(payload, FIELD_ALIASES["availableDays"]):
        available_days = _list_value(payload, FIELD_ALIASES["availableDays"])
        if not available_days:
            raise ApiError("Select at least one available day.", 422, "minimum_one_day")
        _validate_catalog_values(available_days, options["weekDayOptions"], "availableDays")
        operational["availableDays"] = available_days

    if _has(payload, FIELD_ALIASES["serviceAreas"]):
        service_areas = _list_value(payload, FIELD_ALIASES["serviceAreas"])
        if not service_areas:
            raise ApiError("Select at least one service area.", 422, "minimum_one_service_area")
        allowed_areas = options["serviceAreaOptionsByCity"].get(application.city, [])
        _validate_catalog_values(service_areas, allowed_areas, "serviceAreas")
        operational["serviceAreas"] = service_areas

    current_start = application.start_time
    current_end = application.end_time
    if _has(payload, FIELD_ALIASES["startTime"]):
        current_start = _validate_time(
            _scalar_value(payload, FIELD_ALIASES["startTime"]), "startTime"
        )
        operational["startTime"] = current_start
    if _has(payload, FIELD_ALIASES["endTime"]):
        current_end = _validate_time(
            _scalar_value(payload, FIELD_ALIASES["endTime"]), "endTime"
        )
        operational["endTime"] = current_end
    if current_start == current_end and ("startTime" in operational or "endTime" in operational):
        raise ApiError("Start and end time cannot be equal.", 422, "invalid_time_range")

    for field, attribute in (
        ("canStayOvernight", "can_stay_overnight"),
        ("availableOnHolidays", "available_on_holidays"),
    ):
        if _has(payload, FIELD_ALIASES[field]):
            value = bool_value(_scalar_value(payload, FIELD_ALIASES[field]))
            operational[field] = value
            setattr(application, attribute, value)

    if "startTime" in operational:
        application.start_time = operational["startTime"]
    if "endTime" in operational:
        application.end_time = operational["endTime"]
    if "availableDays" in operational:
        _replace_application_items(application, "available_days", operational["availableDays"])
    if "serviceAreas" in operational:
        _replace_application_items(application, "service_areas", operational["serviceAreas"])

    profile = CaregiverProfile.query.filter_by(user_id=application.user_id).first()
    _apply_operational_to_profile(profile, operational)

    review_changes = {}
    if _has(payload, FIELD_ALIASES["experienceLevel"]):
        experience_level = str(
            _scalar_value(payload, FIELD_ALIASES["experienceLevel"], "") or ""
        ).strip()
        _validate_catalog_values(
            [experience_level], options["experienceOptions"], "experienceLevel"
        )
        if application.status == "approved":
            review_changes["experienceLevel"] = experience_level
        else:
            application.experience_level = experience_level

    if _has(payload, FIELD_ALIASES["skills"]):
        skills = _list_value(payload, FIELD_ALIASES["skills"])
        if not skills:
            raise ApiError("Select at least one skill.", 422, "minimum_one_skill")
        _validate_catalog_values(skills, options["skillOptions"], "skills")
        if application.status == "approved":
            review_changes["skills"] = skills
        else:
            _replace_application_items(application, "skills", skills)

    if _has(payload, FIELD_ALIASES["certificates"]):
        certificates = _list_value(payload, FIELD_ALIASES["certificates"])
        _validate_catalog_values(certificates, options["certificateOptions"], "certificates")
        current_certificates = grouped["certificates"]
        merged_certificates = _clean_values(current_certificates + certificates)
        if application.status == "approved":
            review_changes["certificates"] = merged_certificates
        else:
            _replace_application_items(application, "certificates", merged_certificates)

    _validate_uploads(file_storages)
    file_ids = _save_certificate_files(application, file_storages)
    if file_ids:
        review_changes["fileIds"] = file_ids

    if review_changes and application.status == "approved":
        _merge_pending_change(application, review_changes)

    db.session.commit()
    return application


def _experience_years(label):
    numbers = re.findall(r"\d+", normalize_digits(label or ""))
    return int(numbers[-1]) if numbers else 0


def _approved_certificate_values(application):
    values = application.grouped_items()["certificates"]
    values.extend(
        file.original_name
        for file in application.files
        if file.review_status == "approved"
    )
    return _clean_values(values)


def _apply_reviewed_change(application, change):
    payload = change.payload
    profile = CaregiverProfile.query.filter_by(user_id=application.user_id).first()

    if "experienceLevel" in payload:
        application.experience_level = payload["experienceLevel"]
        if profile:
            profile.experience_level = payload["experienceLevel"]
            profile.experience_years = _experience_years(payload["experienceLevel"])

    if "skills" in payload:
        skills = _clean_values(payload["skills"])
        _replace_application_items(application, "skills", skills)
        if profile:
            _replace_profile_relationship(profile, "skills", skills)

    if "certificates" in payload:
        _replace_application_items(
            application,
            "certificates",
            _clean_values(payload["certificates"]),
        )

    for file_id in payload.get("fileIds", []):
        file_record = db.session.get(CaregiverApplicationFile, int(file_id))
        if file_record and file_record.application_id == application.id:
            file_record.review_status = "approved"

    if profile:
        approved_certificates = _approved_certificate_values(application)
        _replace_profile_relationship(profile, "certificates", approved_certificates)


def review_caregiver_application_change(
    application_id,
    change_id,
    status,
    review_note="",
    reviewed_by="system",
):
    application = db.session.get(CaregiverApplication, application_id)
    if not application:
        raise ApiError("Caregiver application was not found.", 404, "application_not_found")
    change = db.session.get(CaregiverApplicationChange, change_id)
    if not change or change.application_id != application.id:
        raise ApiError("Profile update was not found.", 404, "profile_update_not_found")
    if change.status != "pending":
        raise ApiError("This profile update has already been reviewed.", 409, "profile_update_already_reviewed")
    if status not in {"approved", "rejected"}:
        raise ApiError(
            "Invalid profile update decision.",
            422,
            "invalid_review_decision",
            {"allowed": ["approved", "rejected"]},
        )

    review_note = str(review_note or "").strip()
    reviewed_by = str(reviewed_by or "system").strip()
    if status == "approved":
        _apply_reviewed_change(application, change)
    else:
        for file_id in change.payload.get("fileIds", []):
            file_record = db.session.get(CaregiverApplicationFile, int(file_id))
            if file_record and file_record.application_id == application.id:
                file_record.review_status = "rejected"

    change.status = status
    change.reviewed_at = utc_now()
    change.review_note = review_note
    change.reviewed_by = reviewed_by
    notification = create_notification(
        application.user_id,
        "Caregiver profile update reviewed",
        (
            "Your caregiver profile update was approved."
            if status == "approved"
            else "Your caregiver profile update needs changes."
        ),
        "caregiver_profile_update",
        "/?view=caregiver-dashboard&tab=profile",
    )
    db.session.commit()
    deliver_notification(notification)
    return application, CaregiverProfile.query.filter_by(user_id=application.user_id).first()
