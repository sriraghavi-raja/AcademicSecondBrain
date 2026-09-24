import unittest
from unittest.mock import patch

from src.services.github_service import GitHubSyncError, InvalidGitHubToken, sync_github, validate_token
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
            "https://api.github.com/user/repos?affiliation=owner&per_page=10&sort=updated": FakeResponse(
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
            result = sync_github("student-1", "ghp_alice_token", requester=requester)

        self.assertEqual(result["repos_scanned"], 2)
        self.assertEqual(result["skills_added"], 2)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(add.call_count, 2)

    def test_resync_uses_same_github_source_reference(self):
        responses = {
            "https://api.github.com/user/repos?affiliation=owner&per_page=1&sort=updated": FakeResponse(
                200, [{"full_name": "alice/one"}]
            ),
            "https://api.github.com/repos/alice/one/languages": FakeResponse(
                200, {"Python": 100}
            ),
        }

        def requester(url, **kwargs):
            return responses[url]

        with patch("src.services.github_service.add_evidence") as add:
            sync_github("student-1", "ghp_alice_token", max_repos=1, requester=requester)

        add.assert_called_once()
        self.assertEqual(add.call_args.kwargs["source_type"], "github")
        self.assertEqual(add.call_args.kwargs["source_ref"], "alice/one")

    def test_the_repo_list_is_fetched_with_the_students_own_token(self):
        """The token, not a username, is what proves whose repos these are — nothing here is
        self-reported.
        """
        seen_headers = {}

        def requester(url, headers, **kwargs):
            seen_headers[url] = headers
            if "user/repos" in url:
                return FakeResponse(200, [{"full_name": "alice/one"}])
            return FakeResponse(200, {"Python": 100})

        with patch("src.services.github_service.add_evidence"):
            sync_github("student-1", "ghp_alice_token", requester=requester)

        for headers in seen_headers.values():
            self.assertEqual(headers["Authorization"], "Bearer ghp_alice_token")

    def test_only_owned_repositories_are_requested_not_ones_merely_collaborated_on(self):
        captured_url = {}

        def requester(url, **kwargs):
            captured_url["url"] = url
            return FakeResponse(200, [])

        with patch("src.services.github_service.add_evidence"):
            sync_github("student-1", "ghp_alice_token", requester=requester)

        self.assertIn("affiliation=owner", captured_url["url"])


class ValidateTokenTests(unittest.TestCase):
    def test_a_working_token_returns_the_github_profile(self):
        def requester(url, headers, **kwargs):
            self.assertEqual(url, "https://api.github.com/user")
            self.assertEqual(headers["Authorization"], "Bearer ghp_good")
            return FakeResponse(200, {"login": "alice"})

        self.assertEqual(validate_token("ghp_good", requester=requester), {"login": "alice"})

    def test_a_rejected_token_raises_invalid_github_token(self):
        def requester(url, **kwargs):
            return FakeResponse(401, {})

        with self.assertRaises(InvalidGitHubToken):
            validate_token("ghp_bad", requester=requester)

    def test_a_forbidden_token_also_raises_invalid_github_token(self):
        def requester(url, **kwargs):
            return FakeResponse(403, {})

        with self.assertRaises(InvalidGitHubToken):
            validate_token("ghp_bad", requester=requester)

    def test_an_upstream_failure_raises_github_sync_error_not_invalid_token(self):
        def requester(url, **kwargs):
            return FakeResponse(500, {})

        with self.assertRaises(GitHubSyncError):
            validate_token("ghp_good", requester=requester)


if __name__ == "__main__":
    unittest.main()