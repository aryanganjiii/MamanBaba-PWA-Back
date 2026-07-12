from app.models.care_request import CareOffer
from app.models.caregiver import CaregiverProfile


def score_caregiver(care_request, caregiver):
    score = 0
    request_needs = {need.value for need in care_request.needs}
    caregiver_skills = {skill.value for skill in caregiver.skills}
    caregiver_areas = {area.value for area in caregiver.service_areas}

    score += len(request_needs & caregiver_skills) * 8
    if care_request.neighborhood in caregiver_areas:
        score += 20
    if care_request.city == caregiver.city:
        score += 10
    if caregiver.hourly_rate and caregiver.hourly_rate <= care_request.budget_amount * 1000:
        score += 6
    score += caregiver.rating * 3
    score += min(caregiver.experience_years, 10)
    return score


def suggested_caregivers(care_request, limit=12):
    caregivers = CaregiverProfile.query.filter_by(public_status="public").all()
    caregivers.sort(key=lambda caregiver: score_caregiver(care_request, caregiver), reverse=True)
    return caregivers[:limit]


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
