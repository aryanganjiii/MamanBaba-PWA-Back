from flask import Blueprint, g, request

from app.errors import ApiError
from app.extensions import db
from app.models.care_request import CareOffer, CareRequest, CareRequestNeed, CareRequestSelectedDay
from app.models.caregiver import CaregiverProfile
from app.models.communication import Notification
from app.services.auth import role_required
from app.services.matching import ensure_suggested_offers, suggested_caregivers
from app.utils.http import get_json_payload, paginate_query, pagination_params, success
from app.utils.validation import as_list, require_fields

bp = Blueprint("care_requests", __name__, url_prefix="/care-requests")


def _owned_request(request_id):
    care_request = CareRequest.query.filter_by(id=request_id, user_id=g.current_user.id).first()
    if not care_request:
        raise ApiError("درخواست پیدا نشد.", 404, "care_request_not_found")
    return care_request


def _build_care_request(payload):
    require_fields(
        payload,
        [
            "province",
            "city",
            "neighborhood",
            "person",
            "age",
            "gender",
            "physicalStatus",
            "presenceType",
            "recurrenceType",
            "startDate",
            "startTime",
            "endTime",
            "budget",
        ],
    )
    care_needs = as_list(payload.get("careNeeds"))
    return CareRequest(
        user_id=g.current_user.id,
        province=payload["province"],
        city=payload["city"],
        neighborhood=payload["neighborhood"],
        person=payload["person"],
        age_range=payload["age"],
        gender=payload["gender"],
        physical_status=payload["physicalStatus"],
        care_notes=payload.get("careNotes", ""),
        presence_type=payload["presenceType"],
        recurrence_type=payload["recurrenceType"],
        start_date=payload["startDate"],
        start_time=payload["startTime"],
        end_time=payload["endTime"],
        end_date_mode=payload.get("endDateMode", ""),
        end_date=payload.get("endDate", ""),
        full_day_pattern=payload.get("fullDayPattern", ""),
        full_day_duration_days=int(payload.get("fullDayDurationDays") or 1),
        weekly_duration_mode=payload.get("weeklyDurationMode", ""),
        duration_weeks=int(payload.get("durationWeeks") or 0),
        budget_amount=int(payload["budget"]),
        status=payload.get("status", "active"),
        title=payload.get("title") or f"مراقبت {payload['presenceType']} {payload['person']}",
        service_type=payload.get("serviceType") or ("، ".join(care_needs[:2]) if care_needs else "مراقبت در منزل"),
    )


@bp.get("")
@role_required("family")
def list_requests():
    status = request.args.get("status", "all")
    query = CareRequest.query.filter_by(user_id=g.current_user.id).order_by(CareRequest.created_at.desc())
    if status == "active":
        query = query.filter(CareRequest.status.in_(["active", "pending"]))
    elif status != "all":
        query = query.filter_by(status=status)
    page, per_page = pagination_params()
    items, meta = paginate_query(query, page, per_page)
    return success(
        {"items": [item.to_card_dict() for item in items]},
        meta=meta,
    )


@bp.post("")
@role_required("family")
def create_request():
    payload = get_json_payload()
    payload = payload.get("data", payload)
    care_request = _build_care_request(payload)
    db.session.add(care_request)
    db.session.flush()

    for value in as_list(payload.get("careNeeds")):
        db.session.add(CareRequestNeed(request_id=care_request.id, value=value))
    for value in as_list(payload.get("selectedDays")):
        db.session.add(CareRequestSelectedDay(request_id=care_request.id, value=value))

    db.session.flush()
    ensure_suggested_offers(care_request, db.session)
    db.session.add(
        Notification(
            user_id=g.current_user.id,
            title="درخواست شما ثبت شد",
            description="درخواست مراقبت شما ثبت شد و مراقبان مناسب پیشنهاد شدند.",
            type="request",
        )
    )
    db.session.commit()
    return success(
        {
            "request": care_request.to_detail_dict(),
            "suggestedCaregivers": [offer.caregiver.to_card_dict() for offer in care_request.offers],
        },
        status=201,
    )


@bp.get("/<int:request_id>")
@role_required("family")
def request_detail(request_id):
    care_request = _owned_request(request_id)
    return success(care_request.to_detail_dict())


@bp.patch("/<int:request_id>/cancel")
@role_required("family")
def cancel_request(request_id):
    care_request = _owned_request(request_id)
    care_request.status = "cancelled"
    db.session.commit()
    return success(care_request.to_card_dict(), message="درخواست لغو شد.")


@bp.get("/<int:request_id>/suggested-caregivers")
@role_required("family")
def request_suggested_caregivers(request_id):
    care_request = _owned_request(request_id)
    if not care_request.offers:
        ensure_suggested_offers(care_request, db.session)
        db.session.commit()
    sort = request.args.get("sort")
    caregivers = [offer.caregiver for offer in care_request.offers]
    if sort == "price-low":
        caregivers.sort(key=lambda item: item.hourly_rate)
    elif sort == "price-high":
        caregivers.sort(key=lambda item: item.hourly_rate, reverse=True)
    elif sort == "experience-high":
        caregivers.sort(key=lambda item: item.experience_years, reverse=True)
    elif sort == "rating-high":
        caregivers.sort(key=lambda item: item.rating, reverse=True)
    return success({"items": [caregiver.to_card_dict() for caregiver in caregivers]})


@bp.post("/<int:request_id>/caregivers/<slug>/collaboration")
@role_required("family")
def request_caregiver_collaboration(request_id, slug):
    care_request = _owned_request(request_id)
    caregiver = CaregiverProfile.query.filter_by(slug=slug, public_status="public").first()
    if not caregiver:
        raise ApiError("مراقب پیدا نشد.", 404, "caregiver_not_found")

    offer = CareOffer.query.filter_by(request_id=care_request.id, caregiver_id=caregiver.id).first()
    if not offer:
        offer = CareOffer(
            request_id=care_request.id,
            caregiver_id=caregiver.id,
            family_user_id=g.current_user.id,
            proposed_rate=caregiver.hourly_rate,
        )
        db.session.add(offer)
    offer.status = "requested"
    offer.message = (get_json_payload() or {}).get("message", "")
    db.session.add(
        Notification(
            user_id=g.current_user.id,
            title="درخواست همکاری ثبت شد",
            description=f"درخواست همکاری با {caregiver.full_name} ثبت شد.",
            type="request",
        )
    )
    db.session.commit()
    return success(offer.to_dict(), status=201)
