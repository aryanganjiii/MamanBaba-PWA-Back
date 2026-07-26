import re
import unicodedata
from dataclasses import dataclass

from app.models.care_request import CareOffer
from app.models.caregiver import CaregiverProfile
from app.utils.validation import as_list, normalize_digits


NEED_SKILL_ALIASES = {
    "کارهای خانه": {
        "کارهای خانه",
        "کمک در انجام کارهای خانه",
        "تهیه غذا",
        "تهیه غذای سبک",
        "خرید منزل",
    },
    "همراهی و هم صحبتی": {
        "همراهی و هم صحبتی",
        "صحبت و همدلی",
        "همراهی سالمند",
        "همراهی روزانه",
        "هم صحبتی",
    },
    "مراقبت شخصی": {
        "مراقبت شخصی",
        "کمک در کارهای شخصی",
        "کمک در بهداشت فردی",
        "بهداشت فردی",
    },
    "کمک حرکتی": {
        "کمک حرکتی",
        "پیاده روی",
        "پیاده روی روزانه",
        "جابجایی سالمند",
    },
    "رفت و آمد": {
        "رفت و آمد",
        "همراهی برای مراجعه پزشکی",
        "همراهی پزشکی",
        "امور بیرون از منزل",
    },
    "مراقبت تخصصی": {
        "مراقبت تخصصی",
        "مراقبت از بیمار",
        "اندازه گیری علائم حیاتی",
        "یادآوری دارو",
        "کمک پرستاری",
        "پرستاری",
    },
    "مراقبت تسکینی": {
        "مراقبت تسکینی",
        "مراقبت از بیمار",
        "مراقبت از سالمند",
        "صحبت و همدلی",
    },
}


def normalize_match_value(value):
    text = unicodedata.normalize("NFKC", normalize_digits(value or ""))
    text = text.replace("ي", "ی").replace("ك", "ک")
    text = text.replace("\u200c", " ").replace("\u200f", " ")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip().casefold()


NORMALIZED_NEED_ALIASES = {
    normalize_match_value(need): {
        normalize_match_value(alias) for alias in aliases
    }
    for need, aliases in NEED_SKILL_ALIASES.items()
}


@dataclass(frozen=True)
class MatchingCriteria:
    province: str
    city: str
    neighborhood: str
    care_needs: tuple[str, ...]
    presence_type: str
    recurrence_type: str
    selected_days: tuple[str, ...]
    start_time: str
    end_time: str
    budget_min_tomans: int
    budget_max_tomans: int


def _budget_to_tomans(value):
    amount = int(normalize_digits(value or 0))
    return amount * 1000 if 0 < amount < 10_000 else amount


def criteria_from_payload(payload):
    legacy_budget = _budget_to_tomans(payload.get("budget"))
    budget_min = _budget_to_tomans(payload.get("budgetMin"))
    budget_max = _budget_to_tomans(payload.get("budgetMax"))
    if not budget_max:
        budget_max = legacy_budget
    return MatchingCriteria(
        province=str(payload.get("province") or ""),
        city=str(payload.get("city") or ""),
        neighborhood=str(payload.get("neighborhood") or ""),
        care_needs=tuple(str(value) for value in as_list(payload.get("careNeeds"))),
        presence_type=str(payload.get("presenceType") or ""),
        recurrence_type=str(payload.get("recurrenceType") or ""),
        selected_days=tuple(
            str(value) for value in as_list(payload.get("selectedDays"))
        ),
        start_time=str(payload.get("startTime") or ""),
        end_time=str(payload.get("endTime") or ""),
        budget_min_tomans=budget_min,
        budget_max_tomans=budget_max,
    )


def criteria_from_care_request(care_request):
    return criteria_from_payload(
        {
            "province": care_request.province,
            "city": care_request.city,
            "neighborhood": care_request.neighborhood,
            "careNeeds": [need.value for need in care_request.needs],
            "presenceType": care_request.presence_type,
            "recurrenceType": care_request.recurrence_type,
            "selectedDays": [day.value for day in care_request.selected_days],
            "startTime": care_request.start_time,
            "endTime": care_request.end_time,
            "budget": care_request.budget_amount,
            "budgetMin": care_request.budget_min_amount,
            "budgetMax": care_request.budget_max_amount,
        }
    )


def _matches_value(requested_value, caregiver_values):
    requested = normalize_match_value(requested_value)
    return not requested or requested in {
        normalize_match_value(value) for value in caregiver_values
    }


def _skill_covers_alias(skill, alias):
    return skill == alias or (
        len(skill) >= 4
        and len(alias) >= 4
        and (skill in alias or alias in skill)
    )


def _need_is_covered(need, caregiver_skills):
    normalized_need = normalize_match_value(need)
    aliases = NORMALIZED_NEED_ALIASES.get(
        normalized_need,
        {normalized_need},
    )
    return any(
        _skill_covers_alias(skill, alias)
        for skill in caregiver_skills
        for alias in aliases
    )


def _covers_location(criteria, caregiver):
    if normalize_match_value(criteria.city) != normalize_match_value(caregiver.city):
        return False

    requested_area = normalize_match_value(criteria.neighborhood)
    if not requested_area:
        return True
    areas = {
        normalize_match_value(area.value) for area in caregiver.service_areas
    }
    whole_city_labels = {
        normalize_match_value(f"تمام مناطق {criteria.city}"),
        normalize_match_value("تمام مناطق"),
    }
    return requested_area in areas or bool(areas & whole_city_labels)


def _time_to_minutes(value):
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", normalize_digits(value or ""))
    if not match:
        return None
    hour, minute = (int(part) for part in match.groups())
    if hour > 23 or minute > 59:
        return None
    return hour * 60 + minute


def _covers_time(criteria, caregiver):
    requested_start = _time_to_minutes(criteria.start_time)
    requested_end = _time_to_minutes(criteria.end_time)
    available_start = _time_to_minutes(caregiver.start_time)
    available_end = _time_to_minutes(caregiver.end_time)
    if None in {
        requested_start,
        requested_end,
        available_start,
        available_end,
    }:
        return True
    if requested_end <= requested_start:
        requested_end += 24 * 60
    if available_end <= available_start:
        available_end += 24 * 60
    if requested_start < available_start and requested_end > 24 * 60:
        requested_start += 24 * 60
        requested_end += 24 * 60
    return available_start <= requested_start and available_end >= requested_end


def caregiver_matches(criteria, caregiver):
    if caregiver.public_status != "public" or not caregiver.verified:
        return False
    if not _covers_location(criteria, caregiver):
        return False

    caregiver_skills = {
        normalize_match_value(skill.value) for skill in caregiver.skills
    }
    if not all(
        _need_is_covered(need, caregiver_skills)
        for need in criteria.care_needs
    ):
        return False
    if not _matches_value(
        criteria.presence_type,
        [item.value for item in caregiver.service_types],
    ):
        return False
    if not _matches_value(
        criteria.recurrence_type,
        [item.value for item in caregiver.collaboration_types],
    ):
        return False

    requested_days = {
        normalize_match_value(day) for day in criteria.selected_days
    }
    available_days = {
        normalize_match_value(day.value) for day in caregiver.available_days
    }
    if requested_days and not requested_days.issubset(available_days):
        return False
    if not _covers_time(criteria, caregiver):
        return False

    if normalize_match_value(criteria.presence_type) == normalize_match_value("ساعتی"):
        if (
            criteria.budget_min_tomans > 0
            and caregiver.hourly_rate < criteria.budget_min_tomans
        ):
            return False
        if (
            criteria.budget_max_tomans > 0
            and caregiver.hourly_rate > criteria.budget_max_tomans
        ):
            return False
    return True


def score_caregiver(criteria, caregiver):
    score = len(criteria.care_needs) * 25
    areas = {
        normalize_match_value(area.value) for area in caregiver.service_areas
    }
    if normalize_match_value(criteria.neighborhood) in areas:
        score += 20
    else:
        score += 12
    if criteria.selected_days:
        score += 10
    if criteria.budget_max_tomans and caregiver.hourly_rate:
        minimum = criteria.budget_min_tomans
        midpoint = minimum + (criteria.budget_max_tomans - minimum) / 2
        difference = abs(caregiver.hourly_rate - midpoint)
        score += max(12 - difference / 50_000, 0)
    score += caregiver.rating * 3
    score += min(caregiver.experience_years, 10)
    return score


def matched_caregivers(criteria, limit=12):
    caregivers = CaregiverProfile.query.filter_by(
        public_status="public",
        verified=True,
    ).all()
    matches = [
        caregiver
        for caregiver in caregivers
        if caregiver_matches(criteria, caregiver)
    ]
    matches.sort(
        key=lambda caregiver: score_caregiver(criteria, caregiver),
        reverse=True,
    )
    return matches[:limit]


def suggested_caregivers(care_request, limit=12):
    return matched_caregivers(
        criteria_from_care_request(care_request),
        limit=limit,
    )


def ensure_suggested_offers(care_request, db_session, limit=4):
    existing_ids = {offer.caregiver_id for offer in care_request.offers}
    for caregiver in suggested_caregivers(care_request, limit=limit):
        if caregiver.id in existing_ids:
            continue
        db_session.add(
            CareOffer(
                request_id=care_request.id,
                caregiver_id=caregiver.id,
                family_user_id=care_request.user_id,
                status="suggested",
                proposed_rate=caregiver.hourly_rate,
            )
        )
