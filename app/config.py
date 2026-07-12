import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///mamanbaba.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]
    OTP_PROVIDER = os.getenv("OTP_PROVIDER", "static").strip().lower()
    OTP_STATIC_CODE = os.getenv("OTP_STATIC_CODE", "12345")
    OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "120"))
    OTP_LENGTH = int(os.getenv("OTP_LENGTH", "5"))
    OTP_DEBUG_RESPONSE = os.getenv("OTP_DEBUG_RESPONSE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    KAVENEGAR_API_KEY = os.getenv("KAVENEGAR_API_KEY", "")
    KAVENEGAR_VERIFY_TEMPLATE = os.getenv("KAVENEGAR_VERIFY_TEMPLATE", "")
    KAVENEGAR_VERIFY_TYPE = os.getenv("KAVENEGAR_VERIFY_TYPE", "sms")
    KAVENEGAR_USE_CURL_FALLBACK = os.getenv("KAVENEGAR_USE_CURL_FALLBACK", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    KAVENEGAR_REQUEST_TIMEOUT_SECONDS = int(os.getenv("KAVENEGAR_REQUEST_TIMEOUT_SECONDS", "10"))
    JWT_EXPIRES_SECONDS = int(os.getenv("JWT_EXPIRES_SECONDS", str(7 * 24 * 3600)))
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))
