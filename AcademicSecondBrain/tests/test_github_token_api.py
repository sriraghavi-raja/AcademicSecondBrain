"""The /api/github/token endpoints: connect, status, disconnect. GitHub itself is never actually
called here — validate_token is patched, since whether GitHub validation works is covered in
test_github_service.py.
"""

import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api import github_token_router
from src.api.auth import get_current_user
from src.rag.registry import github_credentials
from src.services.auth_service import AuthService
from src.services.github_service import InvalidGitHubToken
from tests.support import IsolatedDatabaseTestCase


class GitHubTokenApiTests(IsolatedDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.app = FastAPI()
        self.app.include_router(github_token_router, dependencies=[Depends(get_current_user)])
        self.auth = AuthService("k" * 32)
        self.app.state.auth_service = self.auth
        self.client = TestClient(self.app)
        self.alice_id, self.alice = self._signup("alice")
        self.bob_id, self.bob = self._signup("bob")

    def _signup(self, name):
        tokens = self.auth.signup(name, f"{name}@example.org", "password-123", "College", "2026")
        return tokens["user"]["user_id"], {"Authorization": f"Bearer {tokens['access_token']}"}

    def test_status_is_disconnected_before_anything_is_saved(self):
        response = self.client.get("/api/github/token", headers=self.alice)

        self.assertEqual(response.json(), {"connected": False})

    def test_connecting_a_valid_token_stores_it_and_flips_status(self):
        with patch("src.api.github.validate_token", return_value={"login": "alice"}) as validate:
            response = self.client.post(
                "/api/github/token", json={"token": "ghp_alice_token"}, headers=self.alice
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"connected": True})
        validate.assert_called_once_with("ghp_alice_token")
        self.assertEqual(github_credentials.get_token(self.alice_id), "ghp_alice_token")
        self.assertEqual(self.client.get("/api/github/token", headers=self.alice).json(), {"connected": True})

    def test_an_invalid_token_is_rejected_and_never_stored(self):
        with patch("src.api.github.validate_token", side_effect=InvalidGitHubToken("bad token")):
            response = self.client.post(
                "/api/github/token", json={"token": "ghp_bad"}, headers=self.alice
            )

        self.assertEqual(response.status_code, 400)
        self.assertIsNone(github_credentials.get_token(self.alice_id))

    def test_the_stored_token_is_never_echoed_back_in_any_response(self):
        with patch("src.api.github.validate_token", return_value={"login": "alice"}):
            post_response = self.client.post(
                "/api/github/token", json={"token": "ghp_alice_token"}, headers=self.alice
            )
        get_response = self.client.get("/api/github/token", headers=self.alice)

        self.assertNotIn("ghp_alice_token", post_response.text)
        self.assertNotIn("ghp_alice_token", get_response.text)

    def test_disconnecting_removes_the_token(self):
        github_credentials.save_token(self.alice_id, "ghp_alice_token")

        response = self.client.delete("/api/github/token", headers=self.alice)

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(github_credentials.get_token(self.alice_id))

    def test_disconnecting_when_nothing_is_connected_still_succeeds(self):
        response = self.client.delete("/api/github/token", headers=self.alice)

        self.assertEqual(response.status_code, 204)

    def test_one_users_token_is_invisible_to_another(self):
        github_credentials.save_token(self.alice_id, "ghp_alice_token")

        self.assertEqual(self.client.get("/api/github/token", headers=self.bob).json(), {"connected": False})

    def test_one_user_cannot_disconnect_anothers_token(self):
        github_credentials.save_token(self.alice_id, "ghp_alice_token")

        self.client.delete("/api/github/token", headers=self.bob)

        self.assertEqual(github_credentials.get_token(self.alice_id), "ghp_alice_token")


if __name__ == "__main__":
    unittest.main()
