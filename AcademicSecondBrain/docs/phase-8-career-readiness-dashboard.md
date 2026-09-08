# Phase 8: Career Readiness Dashboard

## Endpoint

```text
GET /api/career/dashboard/{student_id}
```

The response aggregates profile, taxonomy skills, study topics, evidence confidence, quiz mastery, achievements, projects, and the latest resume/gap-analysis runs. Empty sections return empty arrays or `null`; a student does not need to complete every previous phase.

## Screen

Open:

```text
http://127.0.0.1:8000/dashboard/demo-student
```

The screen is backend-served so it does not introduce a frontend framework or affect the existing APIs. It contains summary metrics, a skill mastery list, weak topics, projects, achievements, and recent career activity.

## Verification

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q main.py src tests
```

For live QA, complete the profile, add a skill, submit quiz attempts, add a project, run gap analysis, generate a resume, and then refresh `/dashboard/demo-student`. Repeat with a new student ID after only creating a profile; the dashboard must still render with zero counts and empty sections.