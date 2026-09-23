"""Public GitHub repository synchronization into the student skill graph."""

import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import requests

from src.services.skill_service import add_evidence
from src.rag.registry.career import upsert_project


class GitHubSyncError(RuntimeError):
    pass


class InvalidGitHubToken(ValueError):
    """The token does not authenticate against GitHub."""


def _request_json(
    url: str,
    headers: dict[str, str],
    requester: Callable[..., Any] = requests.get,
) -> Any:
    response = requester(url, headers=headers, timeout=15)
    if response.status_code >= 400:
        raise GitHubSyncError(f"GitHub request failed with HTTP {response.status_code}")
    return response.json()


def validate_token(token: str, requester: Callable[..., Any] = requests.get) -> dict:
    """Confirms a token actually authenticates against GitHub before we store it. Returns the
    /user payload (the account it belongs to), so the caller can show who just connected.
    """
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"}
    response = requester("https://api.github.com/user", headers=headers, timeout=15)
    if response.status_code in (401, 403):
        raise InvalidGitHubToken("GitHub rejected this token")
    if response.status_code >= 400:
        raise GitHubSyncError(f"GitHub request failed with HTTP {response.status_code}")
    return response.json()


def sync_github(
    student_id: str,
    github_username: str,
    max_repos: Optional[int] = None,
    token: Optional[str] = None,
    requester: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Synchronize public repositories and language evidence incrementally."""
    if not github_username.strip():
        raise ValueError("github_username is required")

    limit = max_repos or int(os.getenv("GITHUB_SYNC_MAX_REPOS", "10"))
    if limit < 1:
        raise ValueError("GITHUB_SYNC_MAX_REPOS must be at least 1")

    headers = {"Accept": "application/vnd.github+json"}
    access_token = token or os.getenv("GITHUB_TOKEN")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    repos = _request_json(
        f"https://api.github.com/users/{github_username.strip()}/repos?per_page={limit}",
        headers,
        requester,
    )
    if not isinstance(repos, list):
        raise GitHubSyncError("GitHub returned an invalid repository response")

    skills_added = 0
    repos_scanned = 0
    errors = []
    for repo in repos[:limit]:
        full_name = repo.get("full_name")
        if not full_name:
            continue
        repos_scanned += 1
        try:
            languages = _request_json(
                f"https://api.github.com/repos/{full_name}/languages",
                headers,
                requester,
            )
            description = repo.get("description") or ""
            upsert_project(
                student_id,
                repo.get("name") or full_name.rsplit("/", 1)[-1],
                ", ".join(languages.keys()),
                "github",
                full_name,
                description,
            )
            for language, byte_count in languages.items():
                confidence = min(1.0, 0.5 + (float(byte_count) / max(sum(languages.values()), 1)) * 0.5)
                try:
                    add_evidence(
                        student_id=student_id,
                        raw_term=language,
                        source_type="github",
                        source_ref=full_name,
                        confidence=confidence,
                    )
                    skills_added += 1
                except ValueError:
                    continue
        except Exception as error:
            errors.append({"repository": full_name, "error": str(error)})

    return {
        "skills_added": skills_added,
        "repos_scanned": repos_scanned,
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
    }