from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.auth import get_current_user
from src.rag.registry.sessions import SessionNotFoundError

router = APIRouter(tags=["Sessions"])


@router.get("/api/chat/sessions")
def get_sessions_endpoint(request: Request, current_user: Annotated[dict, Depends(get_current_user)]):
    """Gets the caller's historical chat sessions for the sidebar keys."""
    return request.app.state.session_service.list_sessions(current_user["user_id"])


@router.get("/api/chat/history/{session_id}")
def get_session_history_endpoint(
    session_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Retrieves the full message history for one of the caller's sessions."""
    try:
        return request.app.state.session_service.get_history(current_user["user_id"], session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/api/chat/session/{session_id}")
def delete_session_endpoint(
    session_id: str,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Deletes one of the caller's chat sessions and its history."""
    try:
        return request.app.state.session_service.delete_session(current_user["user_id"], session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
