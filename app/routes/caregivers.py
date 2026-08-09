from flask import Blueprint, g, request

from app.errors import ApiError
from app.extensions import db
from app.models.care_request import CareOffer, CareRequest
from app.models.caregiver import CaregiverProfile, CaregiverReview, FavoriteCaregiver
from app.models.communication import Conversation, Message
from app.services.auth import auth_required, role_required
from app.services.notifications import create_notification, deliver_notification
from app.services.matching import criteria_from_payload, matched_caregivers
from app.utils.http import get_json_payload, paginate_query, pagination_params, success
from app.utils.validation import bool_value, require_fields

bp = Blueprint("caregivers", __name__, url_prefix="/caregivers")


def _current_caregiver_profile():
    caregiver = CaregiverProfile.query.filter_by(user_id=g.current_user.id).first()
    if not caregiver or caregiver.public_status != "public":
        raise ApiError(
            "پروفایل مراقب هنوز تأیید و فعال نشده است.",
            403,
            "caregiver_not_approved",
            {"status": g.current_user.caregiver_status},
        )
    return caregiver


def _caregiver_offer_dict(offer):
    care_request = offer.care_request
    status_map = {
        "suggested": "new",
        "requested": "new",
        "pending": "pending",
        "accepted": "accepted",
        "rejected": "rejected",
    }
    return {
        "id": offer.id,
        "title": care_request.title if care_request else "درخواست همکاری مستقیم",
        "person": care_request.service_type if care_request else "",
        "date": care_request.date_label if care_request else "",
        "time": care_request.time_label if care_request else "",
        "location": care_request.location_label if care_request else "",
        "price": f"{offer.proposed_rate or 0:,}",
        "status": status_map.get(offer.status, "pending"),
    }


@bp.get("/me/dashboard")
@role_required("caregiver")
def caregiver_dashboard():
    caregiver = _current_caregiver_profile()
    offers = (
        CareOffer.query.filter_by(caregiver_id=caregiver.id)
        .order_by(CareOffer.created_at.desc())
        .all()
    )
    completed_jobs = sum(
        1
        for offer in offers
        if offer.status == "accepted"
        and offer.care_request
        and offer.care_request.status == "completed"
    )
    return success(
        {
            "profile": {
                "name": caregiver.full_name,
                "phone": g.current_user.phone,
                "city": caregiver.city,
                "rating": f"{caregiver.rating:.1f}",
                "completedJobs": completed_jobs,
                "experience": caregiver.experience_years,
                "isVerified": caregiver.verified,
                "isActive": caregiver.is_available,
            },
            "offers": [_caregiver_offer_dict(offer) for offer in offers],
        }
    )


@bp.patch("/me/status")
@role_required("caregiver")
def update_caregiver_status():
    payload = get_json_payload()
    raw_value = payload.get("isActive", payload.get("active"))
    if raw_value is None:
        raise ApiError(
            "isActive is required.",
            422,
            "missing_fields",
            {"fields": ["isActive"]},
        )
    if not isinstance(raw_value, bool) and str(raw_value).strip().lower() not in {
        "1",
        "0",
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
    }:
        raise ApiError("isActive must be a boolean.", 422, "invalid_boolean")

    caregiver = _current_caregiver_profile()
    caregiver.is_available = bool_value(raw_value)
    db.session.commit()
    return success(
        {
            "isActive": caregiver.is_available,
            "status": "active" if caregiver.is_available else "inactive",
        }
    )


@bp.post("/me/offers/<int:offer_id>/accept")
@role_required("caregiver")
def accept_caregiver_offer(offer_id):
    caregiver = _current_caregiver_profile()
    offer = CareOffer.query.filter_by(id=offer_id, caregiver_id=caregiver.id).first()
    if not offer:
        raise ApiError("پیشنهاد کاری پیدا نشد.", 404, "caregiver_offer_not_found")
    if offer.status == "rejected":
        raise ApiError("پیشنهاد ردشده قابل پذیرش نیست.", 409, "offer_already_rejected")
    offer.status = "accepted"
    notification = create_notification(
        offer.family_user_id,
        "مراقب درخواست شما را پذیرفت",
        f"{caregiver.full_name} درخواست همکاری شما را پذیرفت.",
        "offer_accepted",
        "/?view=home-placeholder&tab=requests",
    )
    db.session.commit()
    deliver_notification(notification)
    return success(_caregiver_offer_dict(offer))


def _caregiver_by_slug(slug):
    caregiver = CaregiverProfile.query.filter_by(
        slug=slug,
        public_status="public",
        is_available=True,
    ).first()
    if not caregiver:
        raise ApiError("مراقب پیدا نشد.", 404, "caregiver_not_found")
    return caregiver


def _favorite_ids(user):
    if not user:
        return set()
    return {
        row.caregiver_id
        for row in FavoriteCaregiver.query.filter_by(user_id=user.id).all()
    }


@bp.get("")
@auth_required(optional=True)
def list_caregivers():
    query = CaregiverProfile.query.filter_by(public_status="public", is_available=True)
    city = request.args.get("city")
    area = request.args.get("area")
    skill = request.args.get("skill")
    sort = request.args.get("sort", request.args.get("sortType", "rating-high"))

    if city:
        query = query.filter_by(city=city)
    if area:
        query = query.join(CaregiverProfile.service_areas).filter_by(value=area)
    if skill:
        query = query.join(CaregiverProfile.skills).filter_by(value=skill)

    if sort == "price-low":
        query = query.order_by(CaregiverProfile.hourly_rate.asc())
    elif sort == "price-high":
        query = query.order_by(CaregiverProfile.hourly_rate.desc())
    elif sort == "experience-high":
        query = query.order_by(CaregiverProfile.experience_years.desc())
    elif sort == "experience-low":
        query = query.order_by(CaregiverProfile.experience_years.asc())
    elif sort == "reviews-high":
        query = query.order_by(CaregiverProfile.review_count.desc())
    else:
        query = query.order_by(CaregiverProfile.rating.desc())

    page, per_page = pagination_params()
    items, meta = paginate_query(query, page, per_page)
    favorite_ids = _favorite_ids(g.current_user)
    return success(
        {
            "items": [
                {
                    **caregiver.to_card_dict(),
                    "isFavorite": caregiver.id in favorite_ids,
                }
                for caregiver in items
            ]
        },
        meta=meta,
    )


@bp.post("/matches")
@auth_required(optional=True)
def match_caregivers():
    payload = get_json_payload()
    payload = payload.get("data", payload)
    require_fields(
        payload,
        [
            "city",
            "neighborhood",
            "presenceType",
            "recurrenceType",
            "startTime",
            "endTime",
        ],
    )
    if not any(
        payload.get(field) not in (None, "")
        for field in ("budget", "budgetMin", "budgetMax")
    ):
        raise ApiError(
            "بازه بودجه الزامی است.",
            422,
            "budget_range_required",
        )
    criteria = criteria_from_payload(payload)
    if (
        criteria.budget_min_tomans < 0
        or criteria.budget_max_tomans <= 0
        or criteria.budget_min_tomans > criteria.budget_max_tomans
    ):
        raise ApiError(
            "بازه بودجه واردشده معتبر نیست.",
            422,
            "invalid_budget_range",
        )
    caregivers = matched_caregivers(criteria)
    favorite_ids = _favorite_ids(g.current_user)
    return success(
        {
            "items": [
                {
                    **caregiver.to_card_dict(),
                    "isFavorite": caregiver.id in favorite_ids,
                }
                for caregiver in caregivers
            ]
        }
    )


@bp.get("/<slug>")
@auth_required(optional=True)
def caregiver_detail(slug):
    caregiver = _caregiver_by_slug(slug)
    is_favorite = bool(g.current_user and caregiver.id in _favorite_ids(g.current_user))
    return success(caregiver.to_detail_dict(favorite=is_favorite))


@bp.post("/<slug>/reviews")
@role_required("family")
def create_review(slug):
    caregiver = _caregiver_by_slug(slug)
    payload = get_json_payload()
    text = (payload.get("text") or payload.get("reviewText") or "").strip()
    if not text:
        raise ApiError("متن نظر الزامی است.", 422, "missing_review_text")
    rating = max(1, min(int(payload.get("rating", 5)), 5))
    review = CaregiverReview(
        caregiver_id=caregiver.id,
        author_user_id=g.current_user.id,
        author_name=g.current_user.full_name or "شما",
        rating=rating,
        text=text,
        display_date="همین حالا",
    )
    db.session.add(review)
    db.session.flush()
    caregiver.refresh_rating()
    notification = None
    if caregiver.user_id:
        notification = create_notification(
            caregiver.user_id,
            "نظر جدید برای پروفایل شما",
            f"{review.author_name} یک نظر {rating} ستاره برای شما ثبت کرد.",
            "review",
            "/?view=caregiver-dashboard&tab=profile",
        )
    db.session.commit()
    deliver_notification(notification)
    return success(review.to_dict(), status=201)


@bp.put("/<slug>/favorite")
@role_required("family")
def set_favorite(slug):
    caregiver = _caregiver_by_slug(slug)
    payload = get_json_payload() if request.is_json else {}
    liked = bool(payload.get("liked", True))
    favorite = FavoriteCaregiver.query.filter_by(user_id=g.current_user.id, caregiver_id=caregiver.id).first()
    if liked and not favorite:
        db.session.add(FavoriteCaregiver(user_id=g.current_user.id, caregiver_id=caregiver.id))
    if not liked and favorite:
        db.session.delete(favorite)
    db.session.commit()
    return success({"caregiverId": caregiver.slug, "isFavorite": liked})


@bp.delete("/<slug>/favorite")
@role_required("family")
def remove_favorite(slug):
    caregiver = _caregiver_by_slug(slug)
    favorite = FavoriteCaregiver.query.filter_by(user_id=g.current_user.id, caregiver_id=caregiver.id).first()
    if favorite:
        db.session.delete(favorite)
        db.session.commit()
    return success({"caregiverId": caregiver.slug, "isFavorite": False})


@bp.post("/<slug>/collaboration")
@role_required("family")
def direct_collaboration(slug):
    caregiver = _caregiver_by_slug(slug)
    payload = get_json_payload() if request.is_json else {}
    request_id = payload.get("requestId")
    care_request = None
    if request_id:
        care_request = CareRequest.query.filter_by(id=request_id, user_id=g.current_user.id).first()
        if not care_request:
            raise ApiError("درخواست مراقبت پیدا نشد.", 404, "care_request_not_found")

    offer = CareOffer(
        request_id=care_request.id if care_request else None,
        caregiver_id=caregiver.id,
        family_user_id=g.current_user.id,
        status="requested",
        proposed_rate=caregiver.hourly_rate,
        message=payload.get("message", ""),
    )
    db.session.add(offer)

    conversation = Conversation.query.filter_by(
        family_user_id=g.current_user.id, caregiver_id=caregiver.id
    ).first()
    if not conversation:
        conversation = Conversation(
            family_user_id=g.current_user.id,
            caregiver_id=caregiver.id,
            type="caregiver",
            role_label="مراقب سالمند",
            online=False,
        )
        db.session.add(conversation)
        db.session.flush()
    db.session.add(
        Message(
            conversation_id=conversation.id,
            sender_user_id=g.current_user.id,
            sender_type="family",
            body=payload.get("message") or "درخواست همکاری با این مراقب ثبت شد.",
            time_label="الان",
        )
    )
    family_notification = create_notification(
        g.current_user.id,
        "درخواست همکاری ارسال شد",
        f"درخواست همکاری برای {caregiver.full_name} ارسال شد.",
        "request",
        "/?view=home-placeholder&tab=requests",
    )
    caregiver_notification = None
    if caregiver.user_id:
        caregiver_notification = create_notification(
            caregiver.user_id,
            "درخواست همکاری جدید",
            f"{g.current_user.full_name or 'یک خانواده'} برای همکاری با شما درخواست فرستاده است.",
            "care_offer",
            "/?view=caregiver-dashboard&tab=offers",
        )
    db.session.commit()
    deliver_notification(family_notification)
    deliver_notification(caregiver_notification)
    return success({"offer": offer.to_dict(), "conversation": conversation.to_dict()}, status=201)
