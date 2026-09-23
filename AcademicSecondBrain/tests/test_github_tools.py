"""build_github_tools: the MCP client construction and the read-only tool allowlist. The MCP
server itself is never actually contacted here — BasicMCPClient/McpToolSpec are patched, since
whether the real GitHub MCP server behaves as documented is outside what a unit test can check.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from src.rag.synthesis.github_tools import ALLOWED_GITHUB_TOOLS, GITHUB_MCP_URL, build_github_tools

KNOWN_WRITE_TOOLS = {
    "create_branch",
    "create_or_update_file",
    "delete_file",
    "push_files",
    "create_repository",
    "delete_repository",
    "fork_repository",
    "issue_write",
    "add_issue_comment",
    "update_issue_comment",
    "sub_issue_write",
    "create_pull_request",
    "update_pull_request",
    "update_pull_request_branch",
    "merge_pull_request",
    "add_comment_to_pending_review",
    "add_reply_to_pull_request_comment",
    "pull_request_review_write",
}


class AllowlistTests(unittest.TestCase):
    def test_the_allowlist_contains_no_known_write_tool(self):
        self.assertEqual(set(ALLOWED_GITHUB_TOOLS) & KNOWN_WRITE_TOOLS, set())

    def test_the_allowlist_is_not_empty(self):
        self.assertTrue(ALLOWED_GITHUB_TOOLS)


class BuildGitHubToolsTests(unittest.TestCase):
    def test_no_token_returns_no_tools_without_contacting_github(self):
        with patch("src.rag.synthesis.github_tools.BasicMCPClient") as client_cls, patch(
            "src.rag.synthesis.github_tools.McpToolSpec"
        ) as spec_cls:
            result = asyncio.run(build_github_tools(None))

        self.assertEqual(result, [])
        client_cls.assert_not_called()
        spec_cls.assert_not_called()

    def test_a_token_builds_a_bearer_scoped_client_restricted_to_the_allowlist(self):
        sentinel_tools = [Mock(name="tool")]
        fake_spec = Mock()
        fake_spec.to_tool_list_async = AsyncMock(return_value=sentinel_tools)

        with patch("src.rag.synthesis.github_tools.BasicMCPClient") as client_cls, patch(
            "src.rag.synthesis.github_tools.McpToolSpec", return_value=fake_spec
        ) as spec_cls:
            client_cls.return_value = Mock()
            result = asyncio.run(build_github_tools("ghp_student_token"))

        client_cls.assert_called_once_with(GITHUB_MCP_URL, headers={"Authorization": "Bearer ghp_student_token"})
        spec_cls.assert_called_once_with(client=client_cls.return_value, allowed_tools=ALLOWED_GITHUB_TOOLS)
        self.assertEqual(result, sentinel_tools)

    def test_a_failure_talking_to_the_mcp_server_degrades_to_no_tools(self):
        fake_spec = Mock()
        fake_spec.to_tool_list_async = AsyncMock(side_effect=ConnectionError("unreachable"))

        with patch("src.rag.synthesis.github_tools.BasicMCPClient"), patch(
            "src.rag.synthesis.github_tools.McpToolSpec", return_value=fake_spec
        ):
            result = asyncio.run(build_github_tools("ghp_student_token"))

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
