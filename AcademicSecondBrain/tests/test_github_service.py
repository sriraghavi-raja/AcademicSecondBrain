import unittest
from unittest.mock import patch

from src.services.github_service import sync_github
from tests.support import IsolatedDatabaseTestCase


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


class GitHubServiceTests(IsolatedDatabaseTestCase):
    def test_sync_maps_languages_and_keeps_partial_progress(self):
        responses = {
            "https://api.github.com/users/alice/repos?per_page=10": FakeResponse(
                200,
                [
                    {"full_name": "alice/one"},
                    {"full_name": "alice/two"},
                ],
            ),
            "https://api.github.com/repos/alice/one/languages": FakeResponse(
                200, {"Python": 100, "HTML": 10}
            ),
            "https://api.github.com/repos/alice/two/languages": FakeResponse(403, {}),
        }

        def requester(url, **kwargs):
            return responses[url]

        with patch("src.services.github_service.add_evidence") as add:
            result = sync_github("student-1", "alice", requester=requester)

        self.assertEqual(result["repos_scanned"], 2)
        self.assertEqual(result["skills_added"], 2)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(add.call_count, 2)

    def test_resync_uses_same_github_source_reference(self):
        responses = {
            "https://api.github.com/users/alice/repos?per_page=1": FakeResponse(
                200, [{"full_name": "alice/one"}]
            ),
            "https://api.github.com/repos/alice/one/languages": FakeResponse(
                200, {"Python": 100}
            ),
        }

        def requester(url, **kwargs):
            return responses[url]

        with patch("src.services.github_service.add_evidence") as add:
            sync_github("student-1", "alice", max_repos=1, requester=requester)

        add.assert_called_once()
        self.assertEqual(add.call_args.kwargs["source_type"], "github")
        self.assertEqual(add.call_args.kwargs["source_ref"], "alice/one")


if __name__ == "__main__":
    unittest.main()