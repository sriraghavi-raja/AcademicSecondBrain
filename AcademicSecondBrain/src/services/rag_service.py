"""Business orchestration for academic chat requests."""

from typing import Any, AsyncIterator, Optional

from src.rag.synthesis.chat import handle_streaming_chat


class RagService:
    def __init__(self, retriever: Any, llm: Any, postprocessors: Any):
        self.retriever = retriever
        self.llm = llm
        self.postprocessors = postprocessors

    def ask(
        self,
        question: str,
        session_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """Return the existing SSE event generator without changing its events."""
        return handle_streaming_chat(
            message=question,
            retriever=self.retriever,
            llm=self.llm,
            session_id=session_id,
            node_postprocessors=self.postprocessors,
        )