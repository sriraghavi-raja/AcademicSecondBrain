# Phase 2: Skill Profile Store

## Identity Decision

This solo/development deployment uses the explicit `{student_id}` path parameter as the student identity for both skill routes. It does not use a global default and does not introduce `X-Student-Id`; future authentication can validate the path identity before the service is called.

## Schema

- `skills(student_id, skill_name, created_at, updated_at)` with a composite primary key.
- `skill_evidence(evidence_id, student_id, skill_name, raw_term, source_type, source_ref, confidence, created_at)` with a foreign key to `skills`.
- `achievements(achievement_id, student_id, name, description, awarded_at, metadata_json, created_at)`.

## Real-Time Test

Start the server normally, then open `http://127.0.0.1:8000/docs`.

Use `POST /api/skills/demo-student/evidence` with:

```json
{
  "raw_term": "python",
  "source_type": "manual",
  "source_ref": "phase-2-test",
  "confidence": 0.8
}
```

Then repeat with `raw_term` set to `py`, a different source reference, and confidence `0.95`. Call `GET /api/skills/demo-student` and verify one `Python` skill contains both distinct evidence records and confidence `0.95`.

Inspect the rows directly:

```powershell
uv run python -c "import sqlite3; c=sqlite3.connect('./registry.db'); print(c.execute('select * from skills').fetchall()); print(c.execute('select * from skill_evidence').fetchall()); print(c.execute('select * from achievements').fetchall())"
```

The existing RAG and REST routes are unchanged in behavior. This phase adds only the skills router, registry, service, taxonomy, and tests.

## Phase 2 Gate

Evidence is idempotent on `(student_id, skill_name, source_type, source_ref)`. Re-syncing the same source updates the existing row rather than adding a duplicate. Run `uv run python -m unittest discover -s tests -v` before proceeding to Phase 3.