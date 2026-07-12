# SQL Database Design

این پروژه با SQLAlchemy مدل‌سازی شده و پیش‌فرض محلی آن SQLite است. با تنظیم `DATABASE_URL` می‌توان همان schema را روی PostgreSQL یا MySQL اجرا کرد.

## Core Tables

- `users`: خانواده، مراقب یا ادمین؛ شامل موبایل، نام، شهر، محله، آواتار و وضعیت تایید.
- `otp_codes`: کدهای ورود یک‌بارمصرف با hash، purpose، زمان انقضا و زمان مصرف.
- `addresses`: آدرس‌های ذخیره‌شده خانواده.

## Care Requests

- `care_requests`: اطلاعات کامل فرم درخواست فرانت، شامل موقعیت، سالمند، زمان‌بندی، بودجه و وضعیت.
- `care_request_needs`: نیازهای مراقبتی چندانتخابی.
- `care_request_selected_days`: روزهای انتخاب‌شده در زمان‌بندی.
- `care_offers`: ارتباط درخواست و مراقب، وضعیت پیشنهاد/درخواست همکاری و نرخ پیشنهادی.

## Caregivers

- `caregiver_profiles`: پروفایل عمومی مراقب، نرخ، امتیاز، تجربه، موقعیت و وضعیت انتشار.
- `caregiver_skills`: مهارت‌ها.
- `caregiver_certificates`: مدارک.
- `caregiver_service_types`: نوع خدمات قابل ارائه.
- `caregiver_collaboration_types`: همکاری یک‌باره/مستمر.
- `caregiver_available_days`: روزهای قابل همکاری.
- `caregiver_service_areas`: محدوده‌های خدمت.
- `caregiver_highlights`: نکته‌های برجسته پروفایل.
- `caregiver_reviews`: نظرات و امتیازها.
- `favorite_caregivers`: علاقه‌مندی خانواده به مراقب.

## Caregiver Registration

- `caregiver_applications`: درخواست همکاری مراقب پیش از تایید.
- `caregiver_application_items`: گزینه‌های چندانتخابی ثبت‌نام با category.
- `caregiver_application_files`: فایل‌های مدرک و تصویرهای آپلودشده.

## Communication

- `notifications`: اعلان‌های خانواده.
- `conversations`: گفتگو با مراقب یا پشتیبانی.
- `messages`: پیام‌های هر گفتگو.

## Payments

- `payments`: پرداخت‌های مربوط به کاربر/درخواست، وضعیت پرداخت و شناسه مرجع.
