# API Contract

## Multi-role authentication

- OTP purpose `login` signs in an existing account without adding a role.
- OTP purpose `request` adds the `family` role.
- OTP purpose `caregiver` adds the `caregiver` role.
- Auth responses include `user.roles` and `user.caregiverStatus`.
- `POST /caregiver-applications` requires the `caregiver` role and derives ownership from the token.
- `GET /caregiver-applications/me` returns the current user's latest application.
- `PATCH /caregiver-applications/{id}/status` is restricted to administrators.
- `GET /caregivers/me/dashboard` returns the approved caregiver dashboard.
- `POST /caregivers/me/offers/{offerId}/accept` accepts an owned work offer.

Base URL: `/api/v1`

برای سازگاری با فرانت‌هایی که `VITE_API_BASE_URL` را فقط تا origin تنظیم کرده‌اند، همین route ها بدون prefix نسخه هم فعال هستند؛ مثلا `/auth/request-otp` کنار `/api/v1/auth/request-otp` کار می‌کند.

تمام پاسخ‌های موفق با شکل زیر برمی‌گردند:

```json
{ "data": {}, "meta": {}, "message": "..." }
```

خطاها:

```json
{ "error": { "code": "invalid_phone", "message": "...", "details": {} } }
```

## Auth

- `POST /auth/request-otp`
  - body: `{ "phone": "09121234567", "purpose": "login" }`
  - در حالت `OTP_PROVIDER=kavenegar` کد از طریق Verify Lookup کاوه‌نگار ارسال می‌شود.
- `POST /auth/verify-otp`
  - body: `{ "phone": "09121234567", "code": "12345" }`
  - returns: `accessToken`, `user`
- `GET /auth/me`

## Catalog

- `GET /catalog/locations`
- `GET /catalog/locations/provinces`
- `GET /catalog/locations/regions?city=تهران`
- `GET /catalog/care-options`
- `GET /catalog/caregiver-registration-options`

## Family

- `GET /family/home`
- `GET /family/profile`
- `PATCH /family/profile`
- `GET /family/addresses`
- `POST /family/addresses`
- `PATCH /family/addresses/{id}`
- `DELETE /family/addresses/{id}`
- `GET /family/favorites`

## Care Requests

- `GET /care-requests?status=all|active|pending|completed|cancelled`
- `POST /care-requests`
  - accepts the frontend `RequestData` shape.
- `GET /care-requests/{id}`
- `PATCH /care-requests/{id}/cancel`
- `GET /care-requests/{id}/suggested-caregivers?sort=price-low`
- `POST /care-requests/{id}/caregivers/{slug}/collaboration`

## Caregivers

- `GET /caregivers?city=تهران&area=منطقه ۱&skill=مراقبت شخصی&sort=rating-high`
- `GET /caregivers/{slug}`
- `POST /caregivers/{slug}/reviews`
- `PUT /caregivers/{slug}/favorite`
- `DELETE /caregivers/{slug}/favorite`
- `POST /caregivers/{slug}/collaboration`

## Caregiver Applications

- `GET /caregiver-applications/options`
- `POST /caregiver-applications`
  - JSON or multipart/form-data.
  - supports `profileImage` and repeated `certificateFiles` in multipart mode.
- `GET /caregiver-applications/{id}`

## Notifications

- `GET /notifications`
- `PATCH /notifications/{id}/read`
- `POST /notifications/mark-all-read`

## Conversations

- `GET /conversations?filter=all|unread|support&q=...`
- `GET /conversations/{id}/messages`
- `POST /conversations/{id}/messages`
- `POST /conversations/support`

## Payments

- `GET /payments`
- `POST /payments`
- `POST /payments/{id}/mark-paid`
