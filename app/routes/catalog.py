from flask import Blueprint, request

from app.errors import ApiError
from app.services.catalog_data import (
    ACTIVE_PROVINCES,
    CAREGIVER_REGISTRATION_OPTIONS,
    CARE_NEEDS,
    CITY_REGIONS,
    SERVICE_SUGGESTIONS,
)
from app.utils.http import success

bp = Blueprint("catalog", __name__, url_prefix="/catalog")


@bp.get("/locations")
def locations():
    return success({"activeProvinces": ACTIVE_PROVINCES, "cityRegions": CITY_REGIONS})


@bp.get("/locations/provinces")
def provinces():
    return success(ACTIVE_PROVINCES)


@bp.get("/locations/regions")
def regions():
    city = request.args.get("city", "")
    if not city:
        raise ApiError("پارامتر city الزامی است.", 422, "missing_city")
    return success({"city": city, "regions": CITY_REGIONS.get(city, [])})


@bp.get("/care-options")
def care_options():
    return success({"careNeeds": CARE_NEEDS, "serviceSuggestions": SERVICE_SUGGESTIONS})


@bp.get("/caregiver-registration-options")
def caregiver_registration_options():
    return success(CAREGIVER_REGISTRATION_OPTIONS)
