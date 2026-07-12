# Kavenegar OTP

ارسال OTP از متد Verify Lookup کاوه‌نگار استفاده می‌کند:

```text
https://api.kavenegar.com/v1/{API-KEY}/verify/lookup.json
```

پارامترهای مورد استفاده:

- `receptor`: شماره موبایل کاربر
- `token`: کد OTP
- `template`: نام الگوی تاییدشده در پنل کاوه‌نگار
- `type`: مقدار `sms`

تنظیمات:

```env
OTP_PROVIDER=kavenegar
OTP_LENGTH=5
OTP_TTL_SECONDS=120
KAVENEGAR_API_KEY=...
KAVENEGAR_VERIFY_TEMPLATE=pejixfitwebotp
KAVENEGAR_REQUEST_TIMEOUT_SECONDS=10
```

برای توسعه محلی بدون پیامک:

```env
OTP_PROVIDER=static
OTP_STATIC_CODE=12345
```
