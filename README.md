# MamanBaba PWA Backend

Backend Flask برای پروژه `MamanBaba-PWA-Front` با API نسخه‌دار، دیتابیس SQL و ساختار ماژولار.

## اجرا

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
flask init-db
flask seed-db
flask run
```

اگر محیط اینترنت ندارد و pip به PyPI وصل نمی‌شود، راهنمای [OFFLINE_SETUP.md](docs/OFFLINE_SETUP.md) را ببینید. پروژه برای `Flask-SQLAlchemy`، `Flask-Migrate`، `flask-cors` و `PyJWT` fallback داخلی دارد و با Flask + SQLAlchemy خام هم بوت می‌شود.

برای نصب کامل در محیط آنلاین:

```bash
python -m pip install -r requirements-full.txt
```

## تست

```bash
python -m unittest discover -s tests
```

## API Base

`http://localhost:5000/api/v1`

ورود:

1. `POST /auth/request-otp` با `{ "phone": "09121234567" }`
2. `POST /auth/verify-otp` با `{ "phone": "09121234567", "code": "12345" }`
3. ارسال هدر `Authorization: Bearer <accessToken>`

## OTP با کاوه‌نگار

در `.env` مقدارهای زیر فعال شده‌اند:

```env
OTP_PROVIDER=kavenegar
KAVENEGAR_API_KEY=...
KAVENEGAR_VERIFY_TEMPLATE=pejixfitwebotp
```

برای تست بدون ارسال پیامک واقعی:

```env
OTP_PROVIDER=static
OTP_STATIC_CODE=12345
```

در حالت کاوه‌نگار، API کد OTP را در پاسخ برنمی‌گرداند مگر اینکه صریحا `OTP_DEBUG_RESPONSE=true` شود.

## بخش‌های پوشش داده‌شده

- Auth و OTP
- پروفایل خانواده، آدرس‌ها و داشبورد خانه
- درخواست‌های مراقبت، پیشنهاد مراقبان، لغو درخواست
- لیست، پروفایل، علاقه‌مندی، نظر و درخواست همکاری با مراقب
- ثبت‌نام مراقب با JSON یا multipart/form-data
- اعلان‌ها
- گفتگوها و پیام‌ها
- پرداخت اولیه و تغییر وضعیت پرداخت
- catalog برای استان/شهر/منطقه و گزینه‌های فرم‌ها

جزئیات endpoint ها در [API.md](docs/API.md) و طراحی دیتابیس در [SQL_SCHEMA.md](docs/SQL_SCHEMA.md) آمده است.
