# Offline Setup

اگر `pip install -r requirements.txt` با خطای اتصال به PyPI شکست خورد، مشکل از اینترنت/پراکسی pip است. روی این سیستم پکیج‌های اصلی در Python اصلی نصب هستند، پس می‌توانید venv را به system packages وصل کنید.

## گزینه پیشنهادی

در PowerShell:

```powershell
deactivate
Remove-Item -Recurse -Force .venv
python -m venv .venv --system-site-packages
.\.venv\Scripts\activate
python -c "import flask, sqlalchemy; print('ok')"
python -m unittest discover -s tests
python -m flask --app wsgi init-db
python -m flask --app wsgi seed-db
python -m flask --app wsgi run --port 5001
```

اگر نمی‌خواهید هنگام تست محلی پیامک واقعی ارسال شود، در `.env` این مقدار را بگذارید:

```env
OTP_PROVIDER=static
OTP_STATIC_CODE=12345
```

اگر نمی‌خواهید venv را حذف کنید، فایل `.venv\pyvenv.cfg` را باز کنید و این مقدار را تغییر دهید:

```text
include-system-site-packages = true
```

بعد یک بار venv را deactivate/activate کنید.

## حالت آنلاین

اگر اینترنت یا mirror داخلی دارید:

```powershell
python -m pip install -r requirements-full.txt
```

برای mirror:

```powershell
python -m pip install -r requirements-full.txt -i https://pypi.org/simple
```
