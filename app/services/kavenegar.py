import json
import shutil
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from flask import current_app

from app.errors import ApiError


def _provider():
    return current_app.config["OTP_PROVIDER"]


def _kavenegar_config():
    api_key = current_app.config["KAVENEGAR_API_KEY"]
    template = current_app.config["KAVENEGAR_VERIFY_TEMPLATE"]
    if not api_key or not template:
        raise ApiError(
            "تنظیمات کاوه‌نگار کامل نیست.",
            500,
            "kavenegar_not_configured",
            {"required": ["KAVENEGAR_API_KEY", "KAVENEGAR_VERIFY_TEMPLATE"]},
        )
    return api_key, template


def send_otp(phone, code):
    if _provider() == "static" or current_app.testing:
        return {"provider": "static", "sent": False}

    if _provider() != "kavenegar":
        raise ApiError("ارائه‌دهنده OTP پشتیبانی نمی‌شود.", 500, "unsupported_otp_provider")

    return send_verify_lookup(phone=phone, token=code)


def send_verify_lookup(phone, token):
    api_key, template = _kavenegar_config()
    encoded_api_key = quote(api_key, safe="")
    endpoint = f"https://api.kavenegar.com/v1/{encoded_api_key}/verify/lookup.json"
    params = {
        "receptor": phone,
        "token": token,
        "template": template,
        "type": current_app.config["KAVENEGAR_VERIFY_TYPE"],
    }
    request = Request(
        endpoint,
        data=urlencode(params).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    try:
        with urlopen(
            request,
            timeout=current_app.config["KAVENEGAR_REQUEST_TIMEOUT_SECONDS"],
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise _kavenegar_error(exc.code, exc.read().decode("utf-8", errors="ignore")) from exc
    except URLError as exc:
        if current_app.config["KAVENEGAR_USE_CURL_FALLBACK"]:
            current_app.logger.warning("Kavenegar urllib failed; trying curl fallback: %s", exc)
            payload = _send_verify_lookup_with_curl(endpoint, params)
        else:
            raise ApiError(
                "اتصال به سرویس کاوه‌نگار برقرار نشد.",
                502,
                "kavenegar_connection_error",
                {"reason": str(exc.reason)},
            ) from exc
    except json.JSONDecodeError as exc:
        raise ApiError(
            "پاسخ کاوه‌نگار قابل پردازش نیست.",
            502,
            "kavenegar_invalid_response",
        ) from exc

    status = int(payload.get("return", {}).get("status", 0) or 0)
    if status != 200:
        raise _kavenegar_error(status, payload.get("return", {}).get("message", ""))

    entries = payload.get("entries", [])
    return {
        "provider": "kavenegar",
        "sent": True,
        "status": status,
        "messageId": entries[0].get("messageid") if entries and isinstance(entries, list) else None,
    }


def _send_verify_lookup_with_curl(endpoint, params):
    curl_path = shutil.which("curl.exe") or shutil.which("curl")
    if not curl_path:
        raise ApiError(
            "اتصال Python به کاوه‌نگار برقرار نشد و curl هم روی سیستم پیدا نشد.",
            502,
            "kavenegar_connection_error",
        )

    command = [
        curl_path,
        "-sS",
        "--max-time",
        str(current_app.config["KAVENEGAR_REQUEST_TIMEOUT_SECONDS"]),
        "-X",
        "POST",
        endpoint,
    ]
    for key, value in params.items():
        command.extend(["--data-urlencode", f"{key}={value}"])

    try:
        completed = subprocess.run(command, capture_output=True, check=False, text=True, timeout=20)
    except subprocess.TimeoutExpired as exc:
        raise ApiError(
            "اتصال به سرویس کاوه‌نگار برقرار نشد.",
            502,
            "kavenegar_connection_error",
            {"reason": "curl_timeout"},
        ) from exc

    if completed.returncode != 0:
        current_app.logger.error("Kavenegar curl fallback failed: %s", completed.stderr)
        raise ApiError(
            "اتصال به سرویس کاوه‌نگار برقرار نشد.",
            502,
            "kavenegar_connection_error",
            {"reason": completed.stderr.strip()[:300]},
        )

    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        current_app.logger.error("Kavenegar curl fallback invalid response: %s", completed.stdout[:300])
        raise ApiError(
            "پاسخ کاوه‌نگار قابل پردازش نیست.",
            502,
            "kavenegar_invalid_response",
        ) from exc


def _kavenegar_error(status, message):
    error_messages = {
        418: "اعتبار حساب کاوه‌نگار کافی نیست.",
        422: "داده‌های ارسالی به کاوه‌نگار قابل پردازش نیست.",
        424: "الگوی پیامک کاوه‌نگار پیدا نشد یا هنوز تایید نشده است.",
        426: "برای استفاده از Verify Lookup باید سرویس پیشرفته کاوه‌نگار فعال باشد.",
        428: "ارسال کد از طریق تماس تلفنی امکان‌پذیر نیست.",
        431: "ساختار کد تایید برای کاوه‌نگار معتبر نیست.",
        432: "پارامتر token در متن الگوی کاوه‌نگار پیدا نشد.",
        607: "تگ انتخابی کاوه‌نگار معتبر نیست.",
    }
    return ApiError(
        error_messages.get(status, "ارسال کد تایید از طریق کاوه‌نگار ناموفق بود."),
        502,
        "kavenegar_send_failed",
        {"status": status, "message": message},
    )
