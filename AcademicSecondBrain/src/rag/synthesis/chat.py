import json
from typing import Dict, Any, Optional, AsyncGenerator
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from src.rag.registry.sessions import get_or_create_session, save_session
from src.rag.synthesis.engine import format_response_with_sources


async def handle_stateless_chat(
        message: str,
        retriever: Any,
        llm: Any,
        session_id: Optional[str] = None,
        node_postprocessors: Optional[list] = None
) -> Dict[str, Any]:
    """
    Stateless chat invocation:
    1. Loads or creates session memory.
    2. Dynamically builds the ChatEngine.
    3. Streams/waits for response.
    4. Saves state and returns.
    """

    # 1. Load Session
    active_session_id, memory = get_or_create_session(session_id)

    # 2. Build Engine Fresh
    chat_engine = CondensePlusContextChatEngine.from_defaults(
        retriever=retriever,
        node_postprocessors=node_postprocessors,
        llm=llm,
        condense_llm=llm,
        memory=memory,
        system_prompt=(
            "You are a strict and precise academic research assistant. "
            "Use the provided document context and conversation history to answer user questions. "
            "Always cite relevant sources and papers when explaining methodology or findings."
        )
    )

    # 3. Generate Response
    raw_response = await chat_engine.achat(message)
    formatted_result = format_response_with_sources(raw_response)

    # 4. Save state back to SQLite
    save_session(active_session_id, memory)

    return {
        "session_id": active_session_id,
        "answer": formatted_result["answer"],
        "sources": formatted_result["sources"]
    }
async def handle_streaming_chat(
    message: str,
    retriever: Any,
    llm: Any,
    session_id: Optional[str] = None,
    node_postprocessors: Optional[list] = None
) -> AsyncGenerator[str, None]:
    """
    Stateless async streaming chat invocation:
    1. Fetches/creates session memory.
    2. Builds CondensePlusContextChatEngine dynamically.
    3. Streams token events and final source metadata via SSE.
    4. Persists updated session state to SQLite.
    """
    # 1. Retrieve or create session
    active_session_id, memory = get_or_create_session(session_id)

    # 2. Instantiate Chat Engine
    chat_engine = CondensePlusContextChatEngine.from_defaults(
        retriever=retriever,
        node_postprocessors=node_postprocessors,
        llm=llm,
        condense_llm=llm,
        memory=memory,
        system_prompt=(
            "You are a strict and precise academic research assistant. "
            "Use the provided document context and conversation history to answer user questions. "
            "Always cite relevant sources and papers when explaining methodology or findings."
        )
    )

    # 3. Stream Response using LlamaIndex async streaming
    response = await chat_engine.astream_chat(message)

    # First, stream the session_id event to the frontend
    yield f"data: {json.dumps({'type': 'session', 'session_id': active_session_id})}\n\n"

    # Stream generated tokens iteratively
    async for token in response.async_response_gen():
        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

    # 4. Extract sources and stream metadata chunk
    formatted = format_response_with_sources(response)
    sources_payload = [
        {
            "file": src["file_name"],
            "page": src.get("page_number", "N/A"),
            # Explicitly cast numpy.float32 to native Python float
            "score": float(src["score"]) if src.get("score") is not None else None
        }
        for src in formatted.get("sources", [])
    ]

    yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload})}\n\n"

    # 5. Persist updated chat history buffer to SQLite
    save_session(active_session_id, memory)

    # Signal completion
    yield "data: [DONE]\n\n"