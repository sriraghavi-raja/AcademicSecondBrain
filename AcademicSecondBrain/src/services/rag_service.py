"""Business orchestration for academic chat requests."""

from typing import Any, AsyncIterator, Optional

from src.rag.registry.sessions import SessionNotFoundError, session_exists
from src.rag.synthesis.chat import handle_streaming_chat


class RagService:
    def __init__(self, retriever_factory: Any, llm: Any, postprocessors: Any):
        self.retriever_factory = retriever_factory
        self.llm = llm
        self.postprocessors = postprocessors

    def ask(
        self,
        user_id: str,
        question: str,
        session_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Return the existing SSE event generator without changing its events.

        Retrieval only ever sees the caller's own documents. A session id the caller does not own raises
        SessionNotFoundError here, before any streaming starts, so the endpoint can still answer with a plain 404.
        """
        if session_id and not session_exists(user_id, session_id):
            raise SessionNotFoundError("Session not found")
        return handle_streaming_chat(
            message=question,
            retriever=self.retriever_factory.for_user(user_id),
            llm=self.llm,
            user_id=user_id,
            session_id=session_id,
            node_postprocessors=self.postprocessors,
        )
