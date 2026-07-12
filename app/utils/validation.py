import json
import re

from app.errors import ApiError

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"


def normalize_digits(value):
    if value is None:
        return ""
    text = str(value)
    for index, digit in enumerate(PERSIAN_DIGITS):
        text = text.replace(digit, str(index))
    for index, digit in enumerate(ARABIC_DIGITS):
        text = text.replace(digit, str(index))
    return text


def normalize_phone(phone):
    phone = normalize_digits(phone)
    phone = re.sub(r"\D", "", phone)
    if phone.startswith("989") and len(phone) == 12:
        phone = "0" + phone[2:]
    if phone.startswith("9") and len(phone) == 10:
        phone = "0" + phone
    return phone


def validate_phone(phone):
    phone = normalize_phone(phone)
    if not re.fullmatch(r"09\d{9}", phone):
        raise ApiError("شماره موبایل معتبر نیست.", 422, "invalid_phone")
    return phone


def require_fields(payload, fields):
    missing = [field for field in fields if payload.get(field) in (None, "", [])]
    if missing:
        raise ApiError(
            "برخی فیلدهای ضروری ارسال نشده‌اند.",
            422,
            "missing_fields",
            {"fields": missing},
        )


def as_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                return parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                return [stripped]
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return [value]


def bool_value(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
