from flask import Blueprint, current_app, g

from app.services.auth import auth_required, create_access_token, issue_otp, verify_otp
from app.utils.http import get_json_payload, success

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.post("/request-otp")
def request_otp():
    payload = get_json_payload()
    otp, code, delivery = issue_otp(payload.get("phone"), payload.get("purpose", "login"))
    data = {
        "phone": otp.phone,
        "purpose": otp.purpose,
        "expiresAt": otp.expires_at.isoformat(),
        "expiresIn": current_app.config["OTP_TTL_SECONDS"],
        "delivery": {
            "provider": delivery.get("provider"),
            "sent": delivery.get("sent"),
        },
    }
    if current_app.testing or current_app.config["OTP_DEBUG_RESPONSE"]:
        data["devCode"] = code
    return success(data, status=201, message="کد تایید ارسال شد.")


@bp.post("/verify-otp")
def verify_otp_route():
    payload = get_json_payload()
    user = verify_otp(payload.get("phone"), payload.get("code"), payload.get("purpose", "login"))
    token = create_access_token(user)
    return success({"accessToken": token, "tokenType": "Bearer", "user": user.to_dict(include_stats=True)})


@bp.get("/me")
@auth_required()
def me():
    return success(g.current_user.to_dict(include_stats=True))
