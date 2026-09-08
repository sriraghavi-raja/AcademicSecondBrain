# Phase 1: Service Layer Extraction

## Scope

This phase moves API orchestration into `src/services/` while reusing the existing `src/rag/` implementation. The RAG pipeline, prompts, retriever algorithms, persistence format, endpoint paths, response payloads, and SSE event strings remain unchanged.

The phase is isolated on branch `feature/service-layer-extraction`. To return to the previous branch:

```powershell
git switch main
```

The existing uncommitted user changes were preserved when the branch was created.

## Service Boundaries

- `RagService.ask()` delegates to `handle_streaming_chat()` and preserves `session`, `token`, `sources`, and `[DONE]` events.
- `DocumentService` owns document mapping, upload persistence, ingestion, BM25 hot-swap, and deletion delegation.
- `SessionService` owns session listing, title generation, history mapping, and deletion delegation.
- API modules only receive HTTP inputs, call the service, construct `StreamingResponse`, and preserve existing exception behavior.

## Automated Test

Run the service-level regression tests:

```powershell
uv run python -m unittest discover -s tests -v
```

These tests mock the existing RAG and registry functions. They verify delegation, response mappings, BM25 hot-swapping, and session behavior without creating a new index or calling external services.

## Manual REST Regression

Run the server from the project root:

```powershell
uv run uvicorn main:app --reload
```

Capture a baseline before future phases and compare it with the current branch. Keep secrets out of captured files.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/docs
Invoke-RestMethod http://127.0.0.1:8000/api/chat/sessions
Invoke-RestMethod http://127.0.0.1:8000/api/chat/history/<session-id>
```

For upload and delete, use Swagger at `http://127.0.0.1:8000/docs` because upload is multipart and chat is SSE. Record status codes and response bodies for:

- `POST /chat` with a new session
- `GET /api/docs`
- `POST /api/docs/upload`
- `DELETE /api/docs/{document_id}`
- `GET /api/chat/sessions`
- `GET /api/chat/history/{session_id}`
- `DELETE /api/chat/session/{session_id}`

For `/chat`, compare the event sequence and JSON fields rather than token timing. The expected event types are `session`, repeated `token`, `sources`, and `[DONE]`.

## Future Phase Rule

Each future phase should have its own branch, implementation folder or clearly owned modules, automated tests, manual verification checklist, and rollback instructions. Do not start the next phase until this phase passes its automated tests and REST regression checks.