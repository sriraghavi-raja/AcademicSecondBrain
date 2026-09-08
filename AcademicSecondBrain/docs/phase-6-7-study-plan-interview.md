# Phases 6 and 7: Study Plans and Mock Interviews

## Phase 6 Live Test

Start the backend:

```powershell
uv run uvicorn main:app --reload
```

In Swagger, call `POST /api/study/plan` with an indexed syllabus document:

```json
{
  "student_id": "demo-student",
  "syllabus_id": "Syllabus.pdf",
  "weak_topics": [
    {"concept_tag": "Python", "accuracy": 0.2}
  ]
}
```

Copy the returned `plan_id`, then call:

```text
GET /api/study/plan/{plan_id}/export
```

Save the downloaded `.ics` file and import it into Google Calendar, Outlook, or Apple Calendar. A weak topic should have more sessions than a normal topic.

## Phase 7 Live Test

Call `POST /api/career/interview/start`:

```json
{"student_id":"demo-student","target_role":"Python Developer","mode":"technical"}
```

Use the returned session ID with `POST /api/career/interview/continue`:

```json
{"session_id":"returned-id","answer":"Python is a programming language."}
```

Finish with `POST /api/career/interview/end`:

```json
{"session_id":"returned-id"}
```

The session uses the existing SQLite memory store with `session_type="interview"`; normal chat sessions remain unchanged.

## Automated Validation

```powershell
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q main.py src tests
```