"""POST /api/skills/sync/github: now uses the caller's own connected PAT instead of a
self-reported username, so it requires a connected GitHub account first.
"""

import unittest
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api import github_router
from src.api.auth import get_current_user
from src.rag.registry import github_credentials
from src.services.auth_service import AuthService
from src.services.github_service import GitHubSyncError
from tests.support import IsolatedDatabaseTestCase


class GitHubSyncApiTests(IsolatedDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.app = FastAPI()
        self.app.include_router(github_router, dependencies=[Depends(get_current_user)])
        self.auth = AuthService("k" * 32)
        self.app.state.auth_service = self.auth
        self.client = TestClient(self.app)
        tokens = self.auth.signup("alice", "alice@example.org", "password-123", "College", "2026")
        self.alice_id = tokens["user"]["user_id"]
        self.alice = {"Authorization": f"Bearer {tokens['access_token']}"}

    def test_syncing_without_a_connected_token_is_rejected(self):
        response = self.client.post("/api/skills/sync/github", headers=self.alice)

        self.assertEqual(response.status_code, 400)

    def test_syncing_uses_the_callers_own_stored_token(self):
        github_credentials.save_token(self.alice_id, "ghp_alice_token")

        with patch(
            "src.api.github.sync_github", return_value={"skills_added": 1, "repos_scanned": 1, "errors": []}
        ) as sync:
            response = self.client.post("/api/skills/sync/github", headers=self.alice)

        self.assertEqual(response.status_code, 200)
        sync.assert_called_once_with(self.alice_id, "ghp_alice_token")

    def test_an_upstream_github_failure_is_a_502(self):
        github_credentials.save_token(self.alice_id, "ghp_alice_token")

        with patch("src.api.github.sync_github", side_effect=GitHubSyncError("boom")):
            response = self.client.post("/api/skills/sync/github", headers=self.alice)

        self.assertEqual(response.status_code, 502)


if __name__ == "__main__":
    unittest.main()
