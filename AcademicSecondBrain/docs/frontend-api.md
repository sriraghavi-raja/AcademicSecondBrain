# Academic Second Brain Frontend API

This document describes the current FastAPI API for frontend integration.

## 1. Connection

Base URL during local development:

```text
http://127.0.0.1:8000
```

The API is served by FastAPI. Interactive API details are also available at:

```text
GET /docs
GET /openapi.json
```

### Browser development and CORS

The backend currently runs on `127.0.0.1:8000`. If the frontend runs on another origin, such as `http://localhost:5173`, configure FastAPI CORS before browser requests are made. Requests from Swagger and server-side tools do not require CORS.

The frontend should call the JSON API directly. The optional backend-served `/dashboard` HTML page is not a replacement for a frontend dashboard and its browser `fetch` call does not manage frontend auth state.

All JSON requests should send:

```http
Content-Type: application/json
```

Except file uploads, which use `multipart/form-data`.

## 2. Authentication

### Public endpoints

These endpoints do not require an access token:

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`

Admin management endpoints require an authenticated user whose role is `admin`.

### Protected endpoints

Every other API endpoint requires:

```http
Authorization: Bearer <access_token>
```

The frontend should store the access token in memory when possible. If persistence across page reloads is required, use a secure strategy appropriate for the deployment. Do not put tokens in URLs.

### User ownership

The backend derives the current student's identity from the JWT `sub` claim. The response field is:

```json
{
  "user_id": "3594f828-14fd-4eaa-b29d-4b66591178a8"
}
```

Frontend code must not send `student_id` for owner-scoped operations. The server uses the authenticated `user_id` automatically.

IDs that still belong in requests are resource IDs, such as `document_id`, `session_id`, `plan_id`, and `syllabus_id`.

## 3. Standard errors

Most errors use this shape:

```json
{
  "detail": "Human-readable error message"
}
```

Common statuses:

| Status | Meaning |
|---|---|
| `400` | Invalid request or business validation failure |
| `401` | Missing, invalid, or expired access token |
| `404` | Requested resource does not exist |
| `409` | Signup conflicts with an existing name or email |
| `422` | FastAPI/Pydantic validation failure |
| `500` | Unexpected server error |
| `502` | External GitHub request failed |
| `503` | RAG/index service is not ready |

`403 Forbidden` means the user is authenticated but does not have permission for the requested action.

Validation errors may have FastAPI's standard shape:

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

## 4. Authentication endpoints

### POST `/api/auth/signup`

Creates a user and returns access and refresh tokens.

Request:

```json
{
  "name": "Raghavi",
  "email": "raghavi@example.com",
  "password": "a-secure-password",
  "confirm_password": "a-secure-password",
  "college_name": "Sri Krishna",
  "college_year": "4th",
  "role": "student"
}
```

Rules:

- `name`: 1-100 characters
- `email`: valid email address
- `password`: 8-72 characters
- `confirm_password` must equal `password`
- `college_name`: 1-200 characters
- `college_year`: 1-20 characters
- `role`: either `student` or `admin`; defaults to `student`

The frontend may show a role selector, but admin creation is protected. To create an admin through signup, the request must include the server-only header below and the backend must have `ADMIN_SIGNUP_KEY` configured:

```http
X-Admin-Signup-Key: <server-only-admin-signup-key>
```

Never expose this key in browser code. Normal frontend signup should always use `"role": "student"`. Admins can later promote users through the protected admin role endpoint.

Success: `201 Created`

```json
{
  "access_token": "jwt-access-token",
  "refresh_token": "opaque-refresh-token",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_expires_at": "2026-10-05T10:13:42+00:00",
  "user": {
    "user_id": "3594f828-14fd-4eaa-b29d-4b66591178a8",
    "name": "Raghavi",
    "email": "raghavi@example.com",
    "college_name": "Sri Krishna",
    "college_year": "4th",
    "role": "student",
    "created_at": "2026-09-05T10:08:49+00:00"
  }
}
```

### POST `/api/auth/login`

Logs in using the user's name and password.

Request:

```json
{
  "name": "Raghavi",
  "password": "a-secure-password"
}
```

Success: `200 OK`. Response has the same token shape as signup.

Failure: `401 Unauthorized`.

### POST `/api/auth/refresh`

Rotates a refresh token and returns a new access token and refresh token. The old refresh token becomes invalid.

Request:

```json
{
  "refresh_token": "opaque-refresh-token"
}
```

Success: `200 OK`, same token response shape as signup.

Frontend behavior:

1. If an API request returns `401` because the access token expired, call refresh once.
2. Replace both stored tokens with the rotated response.
3. Retry the original request once.
4. If refresh fails, clear auth state and send the user to login.

### POST `/api/auth/logout`

Revokes the supplied refresh token.

Request:

```json
{
  "refresh_token": "opaque-refresh-token"
}
```

Success: `204 No Content`.

The frontend should clear local auth state after this request. The short-lived access token may technically remain valid until its expiry; refresh-token reuse is blocked.

### GET `/api/auth/me`

Returns the authenticated user.

Headers:

```http
Authorization: Bearer <access_token>
```

Success:

```json
{
  "user_id": "3594f828-14fd-4eaa-b29d-4b66591178a8",
  "name": "Raghavi",
  "email": "raghavi@example.com",
  "college_name": "Sri Krishna",
  "college_year": "4th",
  "created_at": "2026-09-05T10:08:49+00:00"
}
```

The `role` field controls frontend navigation only as a convenience. The backend remains the authority for authorization.

## 5. Admin endpoints

Admin endpoints require:

```http
Authorization: Bearer <admin-access-token>
```

Students receive `403 Forbidden` from these routes. Admin endpoints do not replace ownership rules on student endpoints.

### GET `/api/admin/users`

Lists users for the admin user-management screen.

Example response:

```json
{
  "users": [
    {
      "user_id": "user-uuid",
      "name": "Raghavi",
      "email": "raghavi@example.com",
      "college_name": "Sri Krishna",
      "college_year": "4th",
      "role": "student",
      "created_at": "2026-09-05T10:08:49+00:00"
    }
  ]
}
```

### GET `/api/admin/users/{user_id}`

Returns one user's account details. This does not return the password hash or refresh tokens.

### PATCH `/api/admin/users/{user_id}/role`

Changes a user's role.

Request:

```json
{
  "role": "admin"
}
```

Allowed role values are `student` and `admin`. An admin cannot remove their own admin role.

### DELETE `/api/admin/users/{user_id}`

Deletes a user account and its refresh sessions. An admin cannot delete their own account.

## 6. Chat and chat sessions

### POST `/chat`

Sends an academic question and receives a Server-Sent Events stream.

Request:

```json
{
  "question": "What are the types of machine learning techniques?",
  "session_id": null,
  "document_id": "machine-learning.pdf"
}
```

Fields:

| Field | Required | Description |
|---|---:|---|
| `question` | Yes | User's question |
| `session_id` | No | One of your own chat sessions. Omit or use `null` to create one. An id that does not exist or belongs to another user returns `404` before any streaming starts |
| `document_id` | No | Restrict retrieval to one uploaded document when supported |

Response headers include:

```http
Content-Type: text/event-stream
```

Each event is separated by a blank line. Parse the `data:` value as JSON.

Session event:

```text
data: {"type":"session","session_id":"session-uuid"}
```

Token event:

```text
data: {"type":"token","content":"Machine learning "}
```

Sources event:

```text
data: {"type":"sources","sources":[{"file":"machine-learning.pdf","page":2,"score":0.91}]}
```

Completion event:

```text
data: [DONE]
```

Frontend recommendation: use `fetch()` and read `response.body.getReader()`. `EventSource` cannot send the normal `Authorization` header, so use `fetch` for this protected SSE endpoint.

### GET `/api/chat/sessions`

Returns the authenticated user's chat sessions for the sidebar. Other users' sessions and mock-interview sessions never appear here.

Example response:

```json
[
  {
    "id": "session-uuid",
    "title": "What are machine learning techniques?",
    "created_at": "2026-09-05T10:20:00"
  }
]
```

### GET `/api/chat/history/{session_id}`

Returns messages for one of the authenticated user's chat sessions. A session that does not exist or belongs to another user returns `404` (the two cases are indistinguishable on purpose), and reading an unknown id no longer creates a session.

Example response:

```json
[
  {
    "id": 1,
    "role": "user",
    "content": "What are supervised learning methods?",
    "timestamp": "2026-09-05T10:20:00"
  },
  {
    "id": 2,
    "role": "assistant",
    "content": "Supervised learning uses labeled examples...",
    "timestamp": "2026-09-05T10:20:00"
  }
]
```

### DELETE `/api/chat/session/{session_id}`

Deletes one of the authenticated user's chat sessions. Returns `404` if it does not exist or belongs to another user.

Success:

```json
{
  "message": "Session deleted"
}
```

## 7. Documents

### GET `/api/docs`

Lists indexed documents.

Example response:

```json
[
  {
    "document_id": "machine-learning.pdf",
    "filename": "machine-learning.pdf",
    "file_path": "uploads/machine-learning.pdf",
    "chunk_count": 12,
    "ingested_at": "unknown"
  }
]
```

### POST `/api/docs/upload`

Uploads and indexes a document.

Request: `multipart/form-data`

Form field:

```text
file: PDF, DOCX, DOC, PPTX, JPG, PNG, or JPEG file
```

Example JavaScript:

```javascript
const form = new FormData();
form.append("file", selectedFile);

const response = await fetch(`${API_BASE}/api/docs/upload`, {
  method: "POST",
  headers: { Authorization: `Bearer ${accessToken}` },
  body: form
});
```

Do not manually set `Content-Type` for `FormData`; the browser adds the multipart boundary.

Success:

```json
{
  "message": "Document ingested successfully",
  "document_id": "machine-learning.pdf",
  "metadata": {
    "added_total_nodes": 20,
    "added_leaf_nodes": 12,
    "file_path": "uploads/machine-learning.pdf"
  }
}
```

### DELETE `/api/docs/{document_id}`

Deletes an indexed document.

Success:

```json
{
  "message": "Document machine-learning.pdf deleted"
}
```

## 8. Skills

All skill endpoints use the authenticated user's `user_id` automatically.

### GET `/api/skills`

Returns the user's skill graph.

Example response:

```json
{
  "skills": [
    {
      "skill_name": "Python",
      "skill_type": "taxonomy",
      "confidence": 0.9,
      "evidence": [
        {
          "evidence_id": 1,
          "raw_term": "Python",
          "source_type": "manual",
          "source_ref": "profile",
          "confidence": 0.9,
          "created_at": "2026-09-05T10:30:00"
        }
      ]
    }
  ]
}
```

### POST `/api/skills/evidence`

Adds or updates evidence for the authenticated user.

Request:

```json
{
  "raw_term": "Python",
  "source_type": "manual",
  "source_ref": "profile",
  "confidence": 0.9
}
```

Rules:

- `raw_term`, `source_type`, and `source_ref` must be non-empty.
- `confidence` must be between `0` and `1`.
- Unknown terms may return `400` if they cannot be matched to the taxonomy.

### POST `/api/skills/sync/github`

Synchronizes public GitHub repositories and programming-language evidence for the authenticated user.

Request:

```json
{
  "github_username": "octocat"
}
```

Example response:

```json
{
  "skills_added": 4,
  "repos_scanned": 8,
  "last_synced_at": "2026-09-05T10:40:00+00:00",
  "errors": []
}
```

A GitHub API failure returns `502`.

## 9. Profile and career

### GET `/api/profile`

Returns the authenticated user's student profile.

Success example:

```json
{
  "student_id": "3594f828-14fd-4eaa-b29d-4b66591178a8",
  "full_name": "Raghavi",
  "email": "raghavi@example.com",
  "phone": "+91 9876543210",
  "location": "Coimbatore",
  "college_name": "Sri Krishna",
  "degree": "B.Tech",
  "branch": "Computer Science",
  "college_start": "2022",
  "college_end": "2026",
  "cgpa": "8.8",
  "school_name": "Example School",
  "school_detail": "Higher Secondary",
  "school_dates": "2020-2022",
  "school_score": "94%"
}
```

If no profile exists: `404`.

### PUT `/api/profile`

Creates or updates the authenticated user's profile.

Request fields:

```json
{
  "full_name": "Raghavi",
  "email": "raghavi@example.com",
  "phone": "+91 9876543210",
  "location": "Coimbatore",
  "college_name": "Sri Krishna",
  "degree": "B.Tech",
  "branch": "Computer Science",
  "college_start": "2022",
  "college_end": "2026",
  "cgpa": "8.8",
  "school_name": "Example School",
  "school_detail": "Higher Secondary",
  "school_dates": "2020-2022",
  "school_score": "94%"
}
```

Only `full_name` is required. Other fields are optional strings.

### GET `/api/career/dashboard`

Returns the authenticated user's combined career and study summary.

The response contains:

```json
{
  "profile": {},
  "summary": {
    "skill_count": 0,
    "project_count": 0,
    "achievement_count": 0,
    "weak_topic_count": 0
  },
  "skills": [],
  "weak_topics": [],
  "projects": [],
  "achievements": [],
  "last_runs": {}
}
```

The exact item fields come from the profile, skill, project, achievement, quiz, and career-run records.

### GET `/dashboard`

Returns the backend-served dashboard HTML page. A frontend application normally does not need this route; use `GET /api/career/dashboard` and build the page in the frontend.

### POST `/api/career/projects`

Adds or updates a manually entered project for the authenticated user.

Request:

```json
{
  "title": "Academic RAG Assistant",
  "tech_stack": "Python, FastAPI",
  "description_text": "Built a document question-answering API."
}
```

Success returns the stored project record, including `project_id`, `student_id`, `source_type`, `source_ref`, and timestamps.

### POST `/api/career/certifications`

Uploads a certificate, extracts its title, issuer, date, and skills, stores it as an achievement, and adds certificate evidence for matched skills.

Request: `multipart/form-data`

```text
file: certificate PDF or supported document/image
```

Success:

```json
{
  "achievement_id": 7,
  "title": "Advanced SQL Certificate",
  "unmatched_skills": []
}
```

If the model does not return a title, the uploaded filename is used as a fallback title.

### POST `/api/career/resume`

Generates and downloads a DOCX resume for the authenticated user.

Request:

```json
{
  "target_role": "Python Developer"
}
```

`target_role` is optional. The response is a file download with content type for a DOCX document.

### POST `/api/career/gap-analysis`

Compares the user's existing skills with skills extracted from a job description.

Request:

```json
{
  "job_description_text": "We need a Python developer with FastAPI, SQL, and GitHub experience."
}
```

Example response:

```json
{
  "student_id": "3594f828-14fd-4eaa-b29d-4b66591178a8",
  "required_skills": ["Python", "SQL"],
  "gaps": [
    {
      "skill_name": "SQL",
      "current_confidence": 0.0
    }
  ]
}
```

### POST `/api/career/interview/start`

Starts a mock interview for the authenticated user.

Request:

```json
{
  "target_role": "Python Developer",
  "mode": "technical"
}
```

Success returns an interview session object containing a `session_id`, question, and session metadata.

### POST `/api/career/interview/continue`

Answers the current interview question.

Request:

```json
{
  "session_id": "interview-session-id",
  "answer": "Python is a high-level programming language."
}
```

The response contains the next interview state/question. Returns `404` if the session does not exist, is not an interview session, or belongs to another user.

### POST `/api/career/interview/end`

Ends an interview.

Request:

```json
{
  "session_id": "interview-session-id"
}
```

The response contains the stored/end state for that interview. Returns `404` if the session does not exist, is not an interview session, or belongs to another user.

## 10. Study system

### POST `/api/study/plan`

Parses a previously indexed syllabus document and creates a study plan for the authenticated user.

Request:

```json
{
  "syllabus_id": "syllabus.pdf",
  "weak_topics": [
    {
      "concept_tag": "Python",
      "accuracy": 0.2
    }
  ]
}
```

`weak_topics` is optional. When omitted, the server uses the user's recorded weak quiz topics.

Success:

```json
{
  "plan_id": "plan-uuid",
  "student_id": "3594f828-14fd-4eaa-b29d-4b66591178a8",
  "syllabus_id": "syllabus.pdf",
  "sessions": [
    {
      "date": "2026-09-05",
      "topic": "Python",
      "source_date_or_week": "Week 1",
      "session_type": "weak-topic-review"
    }
  ]
}
```

The `syllabus_id` must refer to an indexed document with parseable syllabus content.

### GET `/api/study/plan/{plan_id}/export`

Downloads a generated plan as an iCalendar `.ics` file.

Response:

```http
Content-Type: text/calendar
Content-Disposition: attachment; filename="study-plan-<plan_id>.ics"
```

### POST `/api/study/quiz`

Generates multiple-choice questions from an indexed document.

Request:

```json
{
  "document_id": "machine-learning.pdf",
  "num_questions": 5
}
```

Rules:

- `document_id` is required.
- `num_questions` defaults to `5`.
- `num_questions` must be between `1` and `20`.

Success:

```json
{
  "document_id": "machine-learning.pdf",
  "requested_count": 5,
  "generated_count": 5,
  "errors": [],
  "questions": [
    {
      "question": "Which method uses labeled data?",
      "options": ["Supervised learning", "...", "...", "..."],
      "correct_option": 0,
      "explanation": "Supervised learning uses labeled examples.",
      "concept_tag": "Machine Learning"
    }
  ]
}
```

Some questions may fail validation; those failures appear in `errors` while valid questions remain in `questions`.

### POST `/api/study/quiz/submit`

Records quiz attempts for the authenticated user.

Request:

```json
{
  "attempts": [
    {
      "document_id": "machine-learning.pdf",
      "concept_tag": "Machine Learning",
      "correct": true
    },
    {
      "document_id": "machine-learning.pdf",
      "concept_tag": "Python",
      "correct": false
    }
  ]
}
```

The frontend must not send `student_id`.

Success:

```json
{
  "results": [
    {
      "attempt_id": 1,
      "student_id": "3594f828-14fd-4eaa-b29d-4b66591178a8",
      "document_id": "machine-learning.pdf",
      "concept_tag": "Machine Learning",
      "correct": true,
      "accuracy": 1.0
    }
  ],
  "errors": []
}
```

Invalid items are isolated into `errors` instead of failing the whole batch.

### GET `/api/study/weak-topics`

Returns weak quiz topics for the authenticated user.

Optional query parameter:

```text
threshold=0.7
```

The threshold must be between `0` and `1`.

Example response:

```json
{
  "student_id": "3594f828-14fd-4eaa-b29d-4b66591178a8",
  "weak_topics": [
    {
      "concept_tag": "Python",
      "accuracy": 0.4,
      "attempt_count": 5,
      "last_answered_at": "2026-09-05T10:45:00"
    }
  ]
}
```

## 11. Health

### GET `/health`

Returns application health and whether the RAG retriever is initialized.

Example response:

```json
{
  "status": "healthy",
  "pipeline_ready": true
}
```

This endpoint is public and should be used by a frontend or deployment monitor for a basic availability check.

## 12. Recommended frontend request helper

```javascript
const API_BASE = "http://127.0.0.1:8000";

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const accessToken = authStore.accessToken;

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // Refresh once, update authStore, then retry the original request.
    // If refresh fails, clear authStore and redirect to login.
  }

  if (!response.ok) {
    let errorBody;
    try {
      errorBody = await response.json();
    } catch {
      errorBody = { detail: response.statusText };
    }
    throw new Error(errorBody.detail || "Request failed");
  }

  return response;
}
```

For JSON:

```javascript
const response = await apiFetch("/api/skills");
const skills = await response.json();
```

For a file download:

```javascript
const response = await apiFetch("/api/career/resume", {
  method: "POST",
  body: JSON.stringify({ target_role: "Python Developer" })
});
const blob = await response.blob();
const downloadUrl = URL.createObjectURL(blob);
```

For a file upload, pass `FormData` and do not set `Content-Type` manually.

## 13. Frontend screen-to-endpoint map

| Frontend screen | Endpoints |
|---|---|
| Login/signup | `/api/auth/signup`, `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout`, `/api/auth/me` |
| Admin dashboard | `/api/admin/users`, `/api/admin/users/{user_id}`, `/api/admin/users/{user_id}/role`, `/api/admin/users/{user_id}` |
| Main chat | `/chat`, `/api/chat/sessions`, `/api/chat/history/{session_id}`, `/api/chat/session/{session_id}` |
| Documents | `/api/docs`, `/api/docs/upload`, `/api/docs/{document_id}` |
| Skills | `/api/skills`, `/api/skills/evidence`, `/api/skills/sync/github` |
| Profile | `/api/profile` |
| Dashboard | `/api/career/dashboard` |
| Projects/certificates | `/api/career/projects`, `/api/career/certifications` |
| Resume and job preparation | `/api/career/resume`, `/api/career/gap-analysis` |
| Mock interview | `/api/career/interview/start`, `/api/career/interview/continue`, `/api/career/interview/end` |
| Study plan | `/api/study/plan`, `/api/study/plan/{plan_id}/export` |
| Quiz | `/api/study/quiz`, `/api/study/quiz/submit`, `/api/study/weak-topics` |
| App availability | `/health` |
