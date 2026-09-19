# Roles and Authorization

This document defines authentication, roles, ownership, and endpoint permissions for Academic Second Brain.

## 1. Roles

The application has exactly two roles:

```text
student
admin
```

Every user has one role stored in the authentication database.

Existing users created before roles were added are migrated automatically to the `student` role.

## 2. Authentication versus authorization

### Authentication

Authentication answers:

```text
Who is this user?
```

The application authenticates users with a JWT access token:

```http
Authorization: Bearer <access_token>
```

The JWT contains the user's ID in `sub` and their role in `role`.

Example:

```json
{
  "sub": "3594f828-14fd-4eaa-b29d-4b66591178a8",
  "role": "student",
  "type": "access",
  "exp": 1788604122
}
```

### Authorization

Authorization answers:

```text
What is this authenticated user allowed to do?
```

Authorization uses two checks:

1. **Role check**: Is the user a student or an admin?
2. **Ownership check**: Does the requested data belong to the logged-in user?

Being logged in does not automatically allow access to every user's data.

## 3. Ownership rule

For student-owned endpoints, the backend derives the owner from the JWT:

```text
JWT.sub -> current_user["user_id"] -> student_id used by services
```

The frontend must not send `student_id` for owner-scoped endpoints.

Correct:

```text
GET /api/skills
GET /api/profile
GET /api/career/dashboard
```

Incorrect:

```text
GET /api/skills/{student_id}
GET /api/profile/{student_id}
```

Resource IDs are still sent when they identify a specific object rather than an owner:

- `document_id`
- `session_id`
- `plan_id`
- `syllabus_id`

### Current ownership coverage

The JWT-derived ownership rule is implemented for skills, profiles, career records, GitHub evidence, quiz attempts, weak topics, study-plan creation, and other student-scoped operations that pass the authenticated user ID into their services.

Chat sessions and mock-interview sessions are owned by the user who created them (`sessions.user_id`). A session that does not exist, belongs to another user, or has another type returns `404`.

Documents are owned through an `owner_id` stamped on every indexed node at upload. Retrieval (vector and BM25), the document list, and document delete only ever see the caller's own nodes, so one user's chat can never retrieve another user's documents.

Each upload gets a server-generated `document_id` recorded with its owner in the `documents` table, and files are stored under `uploads/<user_id>/<document_id>/` with a fixed name, so two users can upload the same filename without touching each other. Quiz generation and syllabus parsing only read the caller's own document.

The study endpoints are owner-scoped too: quizzes and study plans only accept the caller's own documents (`404` otherwise), parsed syllabus topics are stored per student, a study plan can only be exported by the user who created it, and quiz attempts are only accepted for the caller's own indexed documents.

Still open: deleting a user does not yet remove their documents, sessions, and career records.

## 4. Student permissions

Students can use their own academic and career features.

| Area | Student permission |
|---|---|
| Authentication | Signup, login, refresh, logout, own account details |
| Profile | View and update own profile |
| Documents | Upload, list, and delete their own documents |
| Chat | Chat over their own documents and manage their own chat sessions |
| Skills | View own skills and add own skill evidence |
| GitHub | Sync own GitHub repositories |
| Study plans | Create own study plans and export them |
| Quizzes | Generate quizzes and submit own attempts |
| Weak topics | View own weak topics |
| Projects | Create projects for own profile |
| Certificates | Upload certificates for own profile |
| Resume | Generate own resume |
| Gap analysis | Analyze job gaps against own skills |
| Interviews | Start, continue, and end own interview sessions |
| Dashboard | View own career dashboard |
| Admin management | Not allowed |

## 5. Admin permissions

Admins can use the normal authenticated application endpoints and can manage users through admin endpoints.

Admin endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/admin/users` | List users |
| `GET` | `/api/admin/users/{user_id}` | View one user's account details |
| `PATCH` | `/api/admin/users/{user_id}/role` | Change a user's role |
| `DELETE` | `/api/admin/users/{user_id}` | Delete another user's account |

Admin endpoints require:

```http
Authorization: Bearer <admin-access_token>
```

A student calling an admin endpoint receives:

```http
403 Forbidden
```

An admin cannot:

- Remove their own admin role
- Delete their own account

These protections prevent accidentally removing the last usable administrator account.

## 6. Complete endpoint permission matrix

### Authentication

| Method | Endpoint | Public | Student | Admin |
|---|---|---:|---:|---:|
| `POST` | `/api/auth/signup` | Yes | Yes | Yes |
| `POST` | `/api/auth/login` | Yes | Yes | Yes |
| `POST` | `/api/auth/refresh` | Yes | Yes | Yes |
| `POST` | `/api/auth/logout` | Yes | Yes | Yes |
| `GET` | `/api/auth/me` | No | Own account | Own account |

### Chat and sessions

| Method | Endpoint | Public | Student | Admin |
|---|---|---:|---:|---:|
| `POST` | `/chat` | No | Own authenticated chat | Authenticated admin chat |
| `GET` | `/api/chat/sessions` | No | Own authenticated sessions | Authenticated admin sessions |
| `GET` | `/api/chat/history/{session_id}` | No | Authenticated session access | Authenticated session access |
| `DELETE` | `/api/chat/session/{session_id}` | No | Authenticated session access | Authenticated session access |

### Documents

| Method | Endpoint | Public | Student | Admin |
|---|---|---:|---:|---:|
| `GET` | `/api/docs` | No | Yes | Yes |
| `POST` | `/api/docs/upload` | No | Yes | Yes |
| `DELETE` | `/api/docs/{document_id}` | No | Yes | Yes |

### Skills and GitHub

| Method | Endpoint | Public | Student | Admin |
|---|---|---:|---:|---:|
| `GET` | `/api/skills` | No | Own skills | Own admin account skills |
| `POST` | `/api/skills/evidence` | No | Add own evidence | Add own evidence |
| `POST` | `/api/skills/sync/github` | No | Sync own GitHub | Sync own GitHub |

### Profile and career

| Method | Endpoint | Public | Student | Admin |
|---|---|---:|---:|---:|
| `GET` | `/api/profile` | No | Own profile | Own admin profile |
| `PUT` | `/api/profile` | No | Update own profile | Update own admin profile |
| `GET` | `/api/career/dashboard` | No | Own dashboard | Own admin dashboard |
| `POST` | `/api/career/projects` | No | Create own project | Create own project |
| `POST` | `/api/career/certifications` | No | Upload own certificate | Upload own certificate |
| `POST` | `/api/career/resume` | No | Generate own resume | Generate own resume |
| `POST` | `/api/career/gap-analysis` | No | Analyze own gaps | Analyze own gaps |
| `POST` | `/api/career/interview/start` | No | Start own interview | Start own interview |
| `POST` | `/api/career/interview/continue` | No | Continue own interview | Continue own interview |
| `POST` | `/api/career/interview/end` | No | End own interview | End own interview |
| `GET` | `/dashboard` | No | Authenticated | Authenticated |

### Study

| Method | Endpoint | Public | Student | Admin |
|---|---|---:|---:|---:|
| `POST` | `/api/study/plan` | No | Create own plan | Create own plan |
| `GET` | `/api/study/plan/{plan_id}/export` | No | Export authenticated plan | Export authenticated plan |
| `POST` | `/api/study/quiz` | No | Generate quiz | Generate quiz |
| `POST` | `/api/study/quiz/submit` | No | Record own attempts | Record own attempts |
| `GET` | `/api/study/weak-topics` | No | View own topics | View own topics |

### Administration

| Method | Endpoint | Public | Student | Admin |
|---|---|---:|---:|---:|
| `GET` | `/api/admin/users` | No | No | Yes |
| `GET` | `/api/admin/users/{user_id}` | No | No | Yes |
| `PATCH` | `/api/admin/users/{user_id}/role` | No | No | Yes |
| `DELETE` | `/api/admin/users/{user_id}` | No | No | Yes |

### Health

| Method | Endpoint | Public | Student | Admin |
|---|---|---:|---:|---:|
| `GET` | `/health` | Yes | Yes | Yes |

`/health` reports application availability and does not expose private student data.

## 7. Signup roles

The signup body supports:

```json
{
  "name": "Raghavi",
  "email": "raghavi@example.com",
  "password": "secure-password",
  "confirm_password": "secure-password",
  "college_name": "Sri Krishna",
  "college_year": "4th",
  "role": "student"
}
```

Allowed role values:

```text
student
admin
```

The default is `student`.

### Admin signup protection

Admin signup requires a server-side environment variable:

```env
ADMIN_SIGNUP_KEY=long-private-server-key
```

The request must include:

```http
X-Admin-Signup-Key: long-private-server-key
```

The key must never be placed in frontend JavaScript, browser storage, or public API documentation used by end users.

If the role is `admin` and the key is missing or invalid, the API returns `403 Forbidden`.

A normal frontend signup should always submit:

```json
{
  "role": "student"
}
```

An existing admin can promote a student using:

```http
PATCH /api/admin/users/{user_id}/role
```

with:

```json
{
  "role": "admin"
}
```

## 8. Frontend behavior

After login, the frontend receives:

```json
{
  "user": {
    "user_id": "user-uuid",
    "name": "Raghavi",
    "email": "raghavi@example.com",
    "role": "student"
  }
}
```

Use the role to select navigation:

### Student navigation

```text
Dashboard
Chat
Documents
Skills
Study
Certificates
Projects
Resume
Mock Interview
Profile
Logout
```

### Admin navigation

```text
Admin Dashboard
Users
Role Management
Logout
```

The frontend can hide navigation items, but hiding a button is not security. The backend must always enforce authorization.

When an endpoint returns `401`:

1. Attempt one refresh-token request.
2. Replace the access and refresh tokens with the rotated values.
3. Retry the original request once.
4. If refresh fails, clear authentication state and redirect to login.

When an endpoint returns `403`:

- Do not retry with the same token.
- Show an authorization message or hide the unavailable feature.
- For admin routes, redirect the student to their normal dashboard.

## 9. Security rules

- Never trust a role sent by the frontend without backend validation.
- Never use a URL `student_id` to decide ownership.
- Deleting a user account does not yet remove that user's stored data; treat orphaned data as a known gap until it does.
- Never expose password hashes or refresh-token hashes in API responses.
- Never expose `ADMIN_SIGNUP_KEY` to the browser.
- Do not put access tokens or refresh tokens in URLs.
- Use HTTPS outside local development.
- Rotate refresh tokens on every refresh.
- Keep access tokens short-lived.
- Re-authenticate after a role change so the frontend receives the current role.

## 10. Implementation references

The role and authorization implementation is located in:

- `src/rag/registry/auth.py`: users, roles, and refresh-session persistence
- `src/services/auth_service.py`: role-aware tokens and admin operations
- `src/api/auth.py`: authentication and role dependencies
- `src/api/admin.py`: admin user-management endpoints
- `main.py`: protected router registration
- `tests/test_auth.py`: role and authorization tests
