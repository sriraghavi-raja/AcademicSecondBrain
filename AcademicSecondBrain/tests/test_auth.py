import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin import router as admin_router
from src.api.auth import get_auth_service, get_current_user
from src.api.auth import router as auth_router
from src.rag.registry import auth as auth_registry
from src.services.auth_service import AuthError, AuthService


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.database_path = Path(tempfile.mktemp(suffix=".db"))
        auth_registry.DB_PATH = str(self.database_path)
        auth_registry.init_db()
        self.service = AuthService("a" * 32)

    def tearDown(self):
        self.database_path.unlink(missing_ok=True)

    def test_signup_login_refresh_and_logout(self):
        signup = self.service.signup("Sri", "sri@example.com", "correct-horse", "Example College", "2026")
        self.assertEqual(signup["user"]["email"], "sri@example.com")
        self.assertEqual(signup["user"]["role"], "student")

        login = self.service.login("sri@example.com", "correct-horse")
        self.assertEqual(self.service.user_from_access_token(login["access_token"])["name"], "Sri")

        refreshed = self.service.refresh(login["refresh_token"])
        self.assertNotEqual(refreshed["refresh_token"], login["refresh_token"])
        self.service.logout(refreshed["refresh_token"])
        with self.assertRaises(AuthError):
            self.service.refresh(refreshed["refresh_token"])

    def test_duplicate_name_and_wrong_password_are_rejected(self):
        self.service.signup("Sri", "sri@example.com", "correct-horse", "Example College", "2026")
        with self.assertRaises(AuthError):
            self.service.signup("Sri", "other@example.com", "correct-horse", "Other College", "2027")
        with self.assertRaises(AuthError):
            self.service.login("sri@example.com", "wrong-password")

    def test_login_with_an_unknown_email_is_rejected(self):
        self.service.signup("Sri", "sri@example.com", "correct-horse", "Example College", "2026")
        with self.assertRaises(AuthError):
            self.service.login("nobody@example.com", "correct-horse")

    def test_login_is_case_insensitive_on_email(self):
        self.service.signup("Sri", "sri@example.com", "correct-horse", "Example College", "2026")
        login = self.service.login("SRI@EXAMPLE.COM", "correct-horse")
        self.assertEqual(login["user"]["email"], "sri@example.com")

    def test_signup_can_create_an_admin_directly_at_the_service_layer(self):
        """No key gate here — that authorization now lives at the API layer (see test_auth.py's
        API-level tests): only an already-authenticated admin can reach the endpoint that passes
        role="admin" through to this method.
        """
        result = self.service.signup(
            "Admin", "admin@example.com", "correct-horse", "Example College", "2026", "admin"
        )
        self.assertEqual(result["user"]["role"], "admin")
        self.assertEqual(self.service.user_from_access_token(result["access_token"])["role"], "admin")

    def test_admin_routes_require_admin_role(self):
        app = FastAPI()
        app.include_router(admin_router)
        app.dependency_overrides[get_auth_service] = lambda: self.service
        app.dependency_overrides[get_current_user] = lambda: {
            "user_id": "student-id", "role": "student"
        }
        with TestClient(app) as client:
            response = client.get("/api/admin/users")
        self.assertEqual(response.status_code, 403)

        app.dependency_overrides[get_current_user] = lambda: {
            "user_id": "admin-id", "role": "admin"
        }
        with TestClient(app) as client:
            response = client.get("/api/admin/users")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"users": []})


class SignupApiTests(unittest.TestCase):
    """The public signup endpoint: no role field exists on it any more, so there is nothing for a
    client to set to become an admin — see AdminCreateUserApiTests for how admin accounts get made.
    """

    def setUp(self):
        self.database_path = Path(tempfile.mktemp(suffix=".db"))
        auth_registry.DB_PATH = str(self.database_path)
        auth_registry.init_db()
        self.service = AuthService("a" * 32)
        self.app = FastAPI()
        self.app.include_router(auth_router)
        self.app.dependency_overrides[get_auth_service] = lambda: self.service
        self.client = TestClient(self.app)

    def tearDown(self):
        self.database_path.unlink(missing_ok=True)

    def _signup_body(self, **overrides):
        body = {
            "name": "Sri",
            "email": "sri@example.com",
            "password": "correct-horse",
            "confirm_password": "correct-horse",
            "college_name": "Example College",
            "college_year": "2026",
        }
        body.update(overrides)
        return body

    def test_public_signup_always_creates_a_student(self):
        response = self.client.post("/api/auth/signup", json=self._signup_body())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["role"], "student")

    def test_a_role_field_in_the_request_body_is_silently_ignored(self):
        response = self.client.post("/api/auth/signup", json=self._signup_body(role="admin"))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["role"], "student")

    def test_no_admin_signup_key_header_is_needed_or_checked(self):
        response = self.client.post(
            "/api/auth/signup",
            json=self._signup_body(),
            headers={"X-Admin-Signup-Key": "anything-at-all"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["role"], "student")


class AdminCreateUserApiTests(unittest.TestCase):
    def setUp(self):
        self.database_path = Path(tempfile.mktemp(suffix=".db"))
        auth_registry.DB_PATH = str(self.database_path)
        auth_registry.init_db()
        self.service = AuthService("a" * 32)
        self.app = FastAPI()
        self.app.include_router(admin_router)
        self.app.dependency_overrides[get_auth_service] = lambda: self.service
        self.client = TestClient(self.app)

    def tearDown(self):
        self.database_path.unlink(missing_ok=True)

    def _as(self, role):
        self.app.dependency_overrides[get_current_user] = lambda: {
            "user_id": "admin-id", "role": role
        }

    def _create_body(self, **overrides):
        body = {
            "name": "New Admin",
            "email": "newadmin@example.com",
            "password": "correct-horse",
            "college_name": "Example College",
            "college_year": "2026",
            "role": "admin",
        }
        body.update(overrides)
        return body

    def test_an_admin_can_create_another_admin(self):
        self._as("admin")
        response = self.client.post("/api/admin/users", json=self._create_body())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["role"], "admin")

    def test_an_admin_can_create_a_student(self):
        self._as("admin")
        response = self.client.post(
            "/api/admin/users", json=self._create_body(email="newstudent@example.com", role="student")
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["role"], "student")

    def test_the_response_never_includes_the_new_users_tokens(self):
        self._as("admin")
        response = self.client.post("/api/admin/users", json=self._create_body())
        self.assertNotIn("access_token", response.json())
        self.assertNotIn("refresh_token", response.json())

    def test_a_student_cannot_create_a_user(self):
        self._as("student")
        response = self.client.post("/api/admin/users", json=self._create_body())
        self.assertEqual(response.status_code, 403)

    def test_duplicate_email_is_rejected(self):
        self._as("admin")
        self.client.post("/api/admin/users", json=self._create_body())
        response = self.client.post("/api/admin/users", json=self._create_body(name="Someone Else"))
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()