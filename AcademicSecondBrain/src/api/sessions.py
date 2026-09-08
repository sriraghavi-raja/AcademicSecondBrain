from fastapi import APIRouter, HTTPException
from fastapi import Request

router = APIRouter(tags=["Sessions"])


@router.get("/api/chat/sessions")
def get_sessions_endpoint(request: Request):
    """Gets all historical chat sessions for the sidebar keys."""
    try:
        return request.app.state.session_service.list_sessions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/chat/history/{session_id}")
def get_session_history_endpoint(session_id: str, request: Request):
    """Retrieves the full message history for a specific session."""
    try:
        return request.app.state.session_service.get_history(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/chat/session/{session_id}")
def delete_session_endpoint(session_id: str, request: Request):
    """Deletes a chat session and its history."""
    try:
        return request.app.state.session_service.delete_session(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))