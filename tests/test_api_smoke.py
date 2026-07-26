import unittest
from io import BytesIO
from subprocess import CompletedProcess
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs

from app import create_app
from app.extensions import db
from app.services.kavenegar import send_verify_lookup
from app.services.caregiver_accounts import review_caregiver_application
from app.services.seed import seed_database
from app.models.user import User
from app.services.schema import upgrade_schema


class ApiSmokeTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "JWT_SECRET_KEY": "test-secret",
                "OTP_PROVIDER": "static",
                "OTP_STATIC_CODE": "12345",
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        seed_database()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self):
        response = self.client.post("/api/v1/auth/request-otp", json={"phone": "09121234567"})
        self.assertEqual(response.status_code, 201)
        response = self.client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": "09121234567", "code": "12345"},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()["data"]["accessToken"]

    def auth_headers(self):
        return {"Authorization": f"Bearer {self.login()}"}

    def test_health_and_catalog(self):
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)
        self.assertEqual(self.client.get("/health").status_code, 200)
        response = self.client.get("/api/v1/catalog/caregiver-registration-options")
        self.assertEqual(response.status_code, 200)
        self.assertIn("skillOptions", response.get_json()["data"])

    def test_schema_upgrade_is_idempotent(self):
        first = upgrade_schema()
        second = upgrade_schema()
        self.assertTrue(first["upgraded"])
        self.assertTrue(second["upgraded"])
        self.assertEqual(second["legacyApplicationsWithoutUser"], 0)

    def test_root_auth_compatibility_and_preflight(self):
        preflight = self.client.options(
            "/auth/request-otp",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(preflight.headers.get("Access-Control-Allow-Origin"), "http://localhost:5173")
        self.assertIn("content-type", preflight.headers.get("Access-Control-Allow-Headers", "").lower())

        response = self.client.post("/auth/request-otp", json={"phone": "09121234567"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["data"]["phone"], "09121234567")

    def test_localhost_cors_is_allowed_for_dev_ports(self):
        preflight = self.client.options(
            "/auth/request-otp",
            headers={
                "Origin": "https://localhost:5174",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(preflight.headers.get("Access-Control-Allow-Origin"), "https://localhost:5174")

    def test_production_frontend_cors_is_allowed(self):
        preflight = self.client.options(
            "/auth/request-otp",
            headers={
                "Origin": "https://app.mamanbaba.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(preflight.status_code, 200)
        self.assertEqual(
            preflight.headers.get("Access-Control-Allow-Origin"),
            "https://app.mamanbaba.com",
        )

    def test_family_home_and_request_flow(self):
        headers = self.auth_headers()
        home = self.client.get("/api/v1/family/home", headers=headers)
        self.assertEqual(home.status_code, 200)
        self.assertIn("activeRequest", home.get_json()["data"])

        payload = {
            "province": "تهران",
            "city": "تهران",
            "neighborhood": "منطقه ۱",
            "person": "مادر",
            "age": "۷۰ تا ۷۹ سال",
            "gender": "خانم",
            "physicalStatus": "به همراهی و کمک سبک نیاز دارد",
            "careNeeds": ["کارهای خانه", "مراقبت شخصی"],
            "careNotes": "نیاز به یادآوری دارو دارد.",
            "presenceType": "ساعتی",
            "recurrenceType": "یک‌باره",
            "startDate": "1405/04/25",
            "startTime": "08:00",
            "endTime": "12:00",
            "selectedDays": [],
            "endDateMode": "نامشخص",
            "budget": 250,
        }
        created = self.client.post("/api/v1/care-requests", json=payload, headers=headers)
        self.assertEqual(created.status_code, 201)
        request_id = created.get_json()["data"]["request"]["id"]

        suggested = self.client.get(
            f"/api/v1/care-requests/{request_id}/suggested-caregivers",
            headers=headers,
        )
        self.assertEqual(suggested.status_code, 200)
        self.assertGreater(len(suggested.get_json()["data"]["items"]), 0)

    def test_caregiver_profile_review_favorite_and_messages(self):
        headers = self.auth_headers()
        caregivers = self.client.get("/api/v1/caregivers", headers=headers)
        self.assertEqual(caregivers.status_code, 200)
        slug = caregivers.get_json()["data"]["items"][0]["slug"]

        detail = self.client.get(f"/api/v1/caregivers/{slug}", headers=headers)
        self.assertEqual(detail.status_code, 200)

        review = self.client.post(
            f"/api/v1/caregivers/{slug}/reviews",
            json={"text": "همکاری بسیار خوبی بود.", "rating": 5},
            headers=headers,
        )
        self.assertEqual(review.status_code, 201)

        favorite = self.client.put(
            f"/api/v1/caregivers/{slug}/favorite",
            json={"liked": True},
            headers=headers,
        )
        self.assertEqual(favorite.status_code, 200)

        conversations = self.client.get("/api/v1/conversations", headers=headers)
        self.assertEqual(conversations.status_code, 200)
        conversation_id = conversations.get_json()["data"]["items"][0]["id"]
        message = self.client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"text": "سلام، لطفا جزئیات را ارسال کنید."},
            headers=headers,
        )
        self.assertEqual(message.status_code, 201)

    def test_caregiver_application_json(self):
        phone = "09123334444"
        requested = self.client.post(
            "/api/v1/auth/request-otp",
            json={"phone": phone, "purpose": "caregiver"},
        )
        self.assertEqual(requested.status_code, 201)
        verified = self.client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": "12345", "purpose": "caregiver"},
        )
        self.assertEqual(verified.status_code, 200)
        caregiver_token = verified.get_json()["data"]["accessToken"]
        caregiver_user = verified.get_json()["data"]["user"]
        self.assertEqual(caregiver_user["roles"], ["caregiver"])
        self.assertEqual(caregiver_user["caregiverStatus"], "not_started")
        caregiver_headers = {"Authorization": f"Bearer {caregiver_token}"}

        payload = {
            "fullName": "لیلا احمدی",
            "nationalCode": "1234567890",
            "birthDate": "1370/01/01",
            "gender": "خانم",
            "maritalStatus": "مجرد",
            "province": "تهران",
            "city": "تهران",
            "experienceLevel": "۳ تا ۵ سال",
            "skills": ["مراقبت از سالمند"],
            "certificates": [],
            "serviceTypes": ["ساعتی"],
            "collaborationTypes": ["مستمر"],
            "availableDays": ["شنبه"],
            "startTime": "08:00",
            "endTime": "16:00",
            "hourlyRate": "250000",
            "serviceAreas": ["منطقه ۱"],
            "aboutMe": "من تجربه مراقبت از سالمندان دارم و با صبر و مسئولیت‌پذیری کار می‌کنم.",
            "acceptedTerms": True,
        }
        response = self.client.post(
            "/api/v1/caregiver-applications",
            json=payload,
            headers=caregiver_headers,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["data"]["status"], "pending_review")
        self.assertEqual(response.get_json()["data"]["userId"], caregiver_user["id"])

        caregiver_only_family_access = self.client.get(
            "/api/v1/family/home",
            headers=caregiver_headers,
        )
        self.assertEqual(caregiver_only_family_access.status_code, 403)

        self.client.post(
            "/api/v1/auth/request-otp",
            json={"phone": phone, "purpose": "request"},
        )
        dual_verified = self.client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": "12345", "purpose": "request"},
        )
        self.assertEqual(dual_verified.status_code, 200)
        self.assertEqual(
            dual_verified.get_json()["data"]["user"]["roles"],
            ["caregiver", "family"],
        )
        self.assertEqual(
            dual_verified.get_json()["data"]["user"]["caregiverStatus"],
            "pending_review",
        )

        self.client.post(
            "/api/v1/auth/request-otp",
            json={"phone": phone, "purpose": "login"},
        )
        generic_login = self.client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": "12345", "purpose": "login"},
        )
        self.assertEqual(generic_login.status_code, 200)
        self.assertEqual(
            generic_login.get_json()["data"]["user"]["roles"],
            ["caregiver", "family"],
        )

        application_id = response.get_json()["data"]["id"]
        review_caregiver_application(application_id, "approved")
        approved_login = self.client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": (
                    f"Bearer {generic_login.get_json()['data']['accessToken']}"
                )
            },
        )
        self.assertEqual(approved_login.status_code, 200)
        self.assertEqual(
            approved_login.get_json()["data"]["caregiverStatus"],
            "approved",
        )
        dashboard = self.client.get(
            "/api/v1/caregivers/me/dashboard",
            headers={
                "Authorization": (
                    f"Bearer {generic_login.get_json()['data']['accessToken']}"
                )
            },
        )
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(
            dashboard.get_json()["data"]["profile"]["name"],
            payload["fullName"],
        )

    def test_generic_login_does_not_create_an_unregistered_account(self):
        phone = "09125556666"
        self.client.post(
            "/api/v1/auth/request-otp",
            json={"phone": phone, "purpose": "login"},
        )
        response = self.client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "code": "12345", "purpose": "login"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "account_not_registered")

    def test_legacy_primary_role_is_preserved_when_second_role_is_added(self):
        user = User(phone="09127778888", role="family", is_verified=True)
        db.session.add(user)
        user.add_role("caregiver")
        db.session.commit()
        self.assertEqual(user.role_names, ["caregiver", "family"])


class KavenegarOtpTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "OTP_PROVIDER": "kavenegar",
                "KAVENEGAR_API_KEY": "key/with/special=chars",
                "KAVENEGAR_VERIFY_TEMPLATE": "pejixfitwebotp",
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_verify_lookup_uses_kavenegar_payload(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return BytesIO(
                    b'{"return":{"status":200,"message":"ok"},"entries":[{"messageid":123}]}'
                ).read()

        with patch("app.services.kavenegar.urlopen", return_value=FakeResponse()) as mocked:
            result = send_verify_lookup("09121234567", "12345")

        request = mocked.call_args.args[0]
        self.assertIn("/verify/lookup.json", request.full_url)
        self.assertEqual(request.get_method(), "POST")
        payload = parse_qs(request.data.decode("utf-8"))
        self.assertEqual(payload["receptor"], ["09121234567"])
        self.assertEqual(payload["token"], ["12345"])
        self.assertEqual(payload["template"], ["pejixfitwebotp"])
        self.assertEqual(payload["type"], ["sms"])
        self.assertEqual(result["provider"], "kavenegar")
        self.assertTrue(result["sent"])
        self.assertEqual(result["messageId"], 123)

    def test_verify_lookup_uses_curl_fallback_when_urllib_fails(self):
        completed = CompletedProcess(
            args=["curl"],
            returncode=0,
            stdout='{"return":{"status":200,"message":"ok"},"entries":[{"messageid":456}]}',
            stderr="",
        )

        with patch("app.services.kavenegar.urlopen", side_effect=URLError("blocked")):
            with patch("app.services.kavenegar.shutil.which", return_value="curl.exe"):
                with patch("app.services.kavenegar.subprocess.run", return_value=completed) as run:
                    result = send_verify_lookup("09121234567", "12345")

        command = run.call_args.args[0]
        self.assertIn("curl.exe", command)
        self.assertIn("--data-urlencode", command)
        self.assertIn("receptor=09121234567", command)
        self.assertTrue(result["sent"])
        self.assertEqual(result["messageId"], 456)


if __name__ == "__main__":
    unittest.main()
