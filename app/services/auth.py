from datetime import datetime, timedelta, timezone
from functools import wraps
import secrets

from flask import current_app, g, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from app.errors import ApiError
from app.extensions import db
from app.models.base import utc_now
from app.models.user import OtpCode, User
from app.services.kavenegar import send_otp
from app.utils.validation import validate_phone

try:
    import jwt
except ImportError:  # pragma: no cover
    jwt = None


AUTH_PURPOSE_ROLES = {
    "request": "family",
    "family": "family",
    "caregiver": "caregiver",
}
ALLOWED_AUTH_PURPOSES = {"login", *AUTH_PURPOSE_ROLES}


def normalize_auth_purpose(purpose):
    value = str(purpose or "login").strip().lower()
    if value not in ALLOWED_AUTH_PURPOSES:
        raise ApiError(
            "هدف ورود معتبر نیست.",
            422,
            "invalid_auth_purpose",
            {"allowed": sorted(ALLOWED_AUTH_PURPOSES)},
        )
    return value


def create_access_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "phone": user.phone,
        "role": user.role,
        "roles": user.role_names,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=current_app.config["JWT_EXPIRES_SECONDS"])).timestamp()),
    }
    if jwt is None:
        serializer = URLSafeTimedSerializer(current_app.config["JWT_SECRET_KEY"], salt="access-token")
        return serializer.dumps(payload)
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def decode_access_token(token):
    if jwt is None:
        serializer = URLSafeTimedSerializer(current_app.config["JWT_SECRET_KEY"], salt="access-token")
        try:
            return serializer.loads(token, max_age=current_app.config["JWT_EXPIRES_SECONDS"])
        except SignatureExpired as exc:
            raise ApiError("نشست شما منقضی شده است.", 401, "token_expired") from exc
        except BadSignature as exc:
            raise ApiError("توکن ورود معتبر نیست.", 401, "invalid_token") from exc

    try:
        return jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise ApiError("نشست شما منقضی شده است.", 401, "token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError("توکن ورود معتبر نیست.", 401, "invalid_token") from exc


def current_user_from_request(optional=False):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        if optional:
            return None
        raise ApiError("برای دسترسی به این بخش وارد حساب شوید.", 401, "auth_required")

    token = header.removeprefix("Bearer ").strip()
    payload = decode_access_token(token)
    user = db.session.get(User, int(payload["sub"]))
    if not user:
        raise ApiError("کاربر یافت نشد.", 401, "user_not_found")
    return user


def auth_required(optional=False):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            g.current_user = current_user_from_request(optional=optional)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def role_required(*required_roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            g.current_user = current_user_from_request()
            if not any(g.current_user.has_role(role) for role in required_roles):
                raise ApiError(
                    "حساب شما اجازه دسترسی به این بخش را ندارد.",
                    403,
                    "role_required",
                    {
                        "requiredRoles": list(required_roles),
                        "userRoles": g.current_user.role_names,
                    },
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def generate_otp_code():
    if current_app.config["OTP_PROVIDER"] == "static" or current_app.testing:
        return current_app.config["OTP_STATIC_CODE"]

    length = max(int(current_app.config["OTP_LENGTH"]), 4)
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


def issue_otp(phone, purpose="login"):
    phone = validate_phone(phone)
    purpose = normalize_auth_purpose(purpose)
    code = generate_otp_code()
    expires_at = utc_now() + timedelta(seconds=current_app.config["OTP_TTL_SECONDS"])

    otp = OtpCode(
        phone=phone,
        code_hash=generate_password_hash(code),
        purpose=purpose,
        expires_at=expires_at,
    )

    delivery = send_otp(phone=phone, code=code)
    db.session.add(otp)
    db.session.commit()
    return otp, code, delivery


def verify_otp(phone, code, purpose="login"):
    phone = validate_phone(phone)
    code = str(code or "").strip()
    purpose = normalize_auth_purpose(purpose)

    otp = (
        OtpCode.query.filter_by(phone=phone, purpose=purpose)
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if not otp or otp.is_expired or otp.is_consumed or not check_password_hash(otp.code_hash, code):
        raise ApiError("کد واردشده صحیح نیست یا منقضی شده است.", 422, "invalid_otp")

    user = User.query.filter_by(phone=phone).first()
    if not user:
        role = AUTH_PURPOSE_ROLES.get(purpose)
        if not role:
            otp.consumed_at = utc_now()
            db.session.commit()
            raise ApiError(
                "حسابی با این شماره ثبت نشده است. ابتدا به‌عنوان خانواده یا مراقب ثبت‌نام کنید.",
                404,
                "account_not_registered",
            )
        user = User(phone=phone, role=role, is_verified=True)
        user.add_role(role)
        db.session.add(user)
    else:
        role = AUTH_PURPOSE_ROLES.get(purpose)
        if role:
            user.add_role(role)

    user.is_verified = True
    user.last_login_at = utc_now()
    otp.consumed_at = utc_now()
    db.session.commit()
    return user
