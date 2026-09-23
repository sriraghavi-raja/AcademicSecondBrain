"""Business orchestration for academic chat requests."""

import os
from typing import Any, AsyncIterator, Optional

from src.rag.registry.sessions import SessionNotFoundError, session_exists
from src.rag.synthesis.agent_chat import handle_agent_chat
from src.rag.synthesis.chat import handle_streaming_chat
from src.rag.synthesis.document_scope import validate_document_ids


class RagService:
    def __init__(
        self,
        retriever_factory: Any,
        llm: Any,
        postprocessors: Any,
        chat_mode: Optional[str] = None,
    ):
        self.retriever_factory = retriever_factory
        self.llm = llm
        self.postprocessors = postprocessors
        # "agent" (the default) gives the model RAG as a tool call it decides when to use.
        # "engine" is the earlier fixed retrieve-then-generate pipeline, kept as a rollback path.
        self.chat_mode = chat_mode or os.getenv("CHAT_MODE", "agent")

    def ask(
        self,
        user_id: str,
        question: str,
        session_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Return the SSE event generator for the configured chat mode.

        Retrieval only ever sees the caller's own documents. A session id the caller does not own, or
        (in agent mode) a document_id that is not one of the caller's own fully indexed documents,
        raises here, before any streaming starts, so the endpoint can still answer with a plain 404.
        """
        if session_id and not session_exists(user_id, session_id):
            raise SessionNotFoundError("Session not found")

        retriever = self.retriever_factory.for_user(user_id)
        if self.chat_mode == "agent":
            allowed_document_ids = validate_document_ids(user_id, [document_id] if document_id else None)
            return handle_agent_chat(
                message=question,
                retriever=retriever,
                llm=self.llm,
                user_id=user_id,
                session_id=session_id,
                allowed_document_ids=allowed_document_ids,
                node_postprocessors=self.postprocessors,
            )
        return handle_streaming_chat(
            message=question,
            retriever=retriever,
            llm=self.llm,
            user_id=user_id,
            session_id=session_id,
            node_postprocessors=self.postprocessors,
        )
