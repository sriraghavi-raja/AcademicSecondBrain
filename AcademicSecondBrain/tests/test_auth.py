import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin import router as admin_router
from src.api.auth import get_auth_service, get_current_user
from src.rag.registry import auth as auth_registry
from src.services.auth_service import AuthError, AuthService, AuthorizationError


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

        login = self.service.login("Sri", "correct-horse")
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
            self.service.login("Sri", "wrong-password")

    def test_admin_signup_requires_server_key(self):
        with self.assertRaises(AuthorizationError):
            self.service.signup(
                "Admin", "admin@example.com", "correct-horse", "Example College", "2026", "admin"
            )

        with patch.dict("os.environ", {"ADMIN_SIGNUP_KEY": "initial-admin-key"}):
            result = self.service.signup(
                "Admin", "admin@example.com", "correct-horse", "Example College", "2026",
                "admin", "initial-admin-key",
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


if __name__ == "__main__":
    unittest.main()