"""Read-only GitHub tools for the chat agent, scoped to one student's own PAT.

The GitHub MCP server also exposes write tools (create_or_update_file, push_files,
merge_pull_request, delete_file, create_repository, ...). We never let the agent see them:
McpToolSpec's allowed_tools filters the tool list before it is ever handed to FunctionAgent, so a
write tool is not just refused if called, it doesn't exist as far as the model is concerned. The
student's own PAT is also expected to be scoped read-only when they create it, as a second,
independent layer, but this allowlist does not rely on that.
"""

import logging
from typing import List, Optional

from llama_index.core.tools import FunctionTool
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec

logger = logging.getLogger(__name__)

GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"

# Deliberately narrow: enough to explore the student's own repos (file contents, structure,
# history, search), nothing from issues, pull requests, releases, or code scanning. Extend this
# list rather than passing allowed_tools=None.
ALLOWED_GITHUB_TOOLS = [
    "get_me",
    "search_repositories",
    "get_repository_tree",
    "get_file_contents",
    "search_code",
    "list_commits",
    "get_commit",
    "list_branches",
]


async def build_github_tools(token: Optional[str]) -> List[FunctionTool]:
    """The student's own read-only GitHub tools, or an empty list if they haven't connected a
    token, or if the MCP server can't be reached right now — a broken GitHub connection should
    never take down the rest of the chat agent.
    """
    if not token:
        return []
    client = BasicMCPClient(GITHUB_MCP_URL, headers={"Authorization": f"Bearer {token}"})
    tool_spec = McpToolSpec(client=client, allowed_tools=ALLOWED_GITHUB_TOOLS)
    try:
        return await tool_spec.to_tool_list_async()
    except Exception:
        logger.exception("Failed to load GitHub MCP tools; continuing without them")
        return []
