# Phase 3: GitHub Skill Connector

## Decisions

- v1 uses public GitHub repositories only; OAuth-private repositories are deferred.
- `GITHUB_TOKEN` is optional and improves GitHub rate limits. Never commit it.
- `GITHUB_SYNC_MAX_REPOS` defaults to `10` and caps repository API calls.
- Each repository is processed independently. A later failure is returned in `errors` while earlier evidence remains committed.

## Configuration

```env
GITHUB_TOKEN=optional-token
GITHUB_SYNC_MAX_REPOS=10
```

## Automated Tests

```powershell
uv sync
uv run python -m unittest discover -s tests -v
```

Tests mock GitHub responses and verify language mapping, partial progress, bounded repository processing, and stable `(github, owner/repo)` evidence references for idempotent resync.

## Live Test

Start the backend:

```powershell
uv run uvicorn main:app --reload
```

In Swagger at `http://127.0.0.1:8000/docs`, call `POST /api/skills/{student_id}/sync/github` with:

```json
{"github_username": "octocat"}
```

Then call `GET /api/skills/{student_id}` and inspect `skills[].evidence` for `source_type: "github"` and repository references. Repeat the sync and confirm the evidence row count does not increase for the same repository and language.

Direct database check:

```powershell
uv run python -c "import sqlite3; c=sqlite3.connect('./registry.db'); print(c.execute(\"select student_id, skill_name, source_type, source_ref, confidence from skill_evidence where source_type='github'\").fetchall()); c.close()"

## Known Follow-ups Before Phase 5

- `skills_added` currently counts successful evidence writes, including idempotent updates. Before Phase 5, distinguish created from updated evidence and report a true new-skill count.
- Unmapped GitHub languages are currently skipped. Before Phase 5, return an `unmapped_languages` list or count so graph completeness is visible.
- Validate these with two real sync calls and compare database counts before and after. The second identical sync must not increase GitHub evidence rows.
```