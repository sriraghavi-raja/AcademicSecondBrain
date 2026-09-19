from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from src.api.auth import get_current_user
from src.api.schemas import ChatRequest
from src.rag.registry.sessions import SessionNotFoundError

router = APIRouter(tags=["Chat"])


@router.post("/chat")
async def chat_stream_endpoint(
    request_data: ChatRequest,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Streamable chat endpoint returning Server-Sent Events (SSE).
    """
    rag_service = getattr(request.app.state, "rag_service", None)
    if rag_service is None:
        raise HTTPException(status_code=503, detail="RAG pipeline is not initialized yet.")

    try:
        event_generator = rag_service.ask(
            user_id=current_user["user_id"],
            question=request_data.question,
            session_id=request_data.session_id,
            document_id=request_data.document_id,
        )
    except SessionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in reverse proxies like Nginx
        }
    )
