"""Agent-mode chat: RAG exposed to the LLM as a tool call it decides when to use, instead of a
fixed retrieve-then-generate pipeline. See chat.py for the earlier fixed-pipeline mode, kept as a
rollback path behind CHAT_MODE=engine.
"""

import json
from typing import Any, AsyncGenerator, FrozenSet, Optional

from llama_index.core.agent.workflow import AgentStream, FunctionAgent, ToolCall, ToolCallResult
from llama_index.core.base.llms.types import ChatMessage, MessageRole

from src.rag.registry import documents as document_registry
from src.rag.registry import github_credentials
from src.rag.registry.sessions import get_or_create_session, save_session
from src.rag.synthesis.agent_tools import build_document_tools
from src.rag.synthesis.github_tools import build_github_tools

SYSTEM_PROMPT = (
    "You are a strict and precise academic research assistant for one student. You have a "
    "search_documents tool over that student's own uploaded material, and a list_documents tool "
    "that names what they have uploaded.\n\n"
    "Call search_documents before answering any question that could be answered from the "
    "student's documents. If it finds nothing relevant, say so plainly, then you may go ahead and "
    "answer from your own general knowledge — just make clear that part of the answer is not from "
    "their documents. Never present general knowledge as if it came from their material. Ordinary "
    "conversation does not need a tool call. Cite the file name (and page, when given) for any "
    "claim that came from a search result.\n\n"
    "When the student has connected their GitHub account, you also have read-only tools over "
    "their own repositories (file contents, structure, commit history, code search). Use them "
    "only when the student asks about their own code or projects — for interview prep, "
    "explaining a repo, or resume-style summaries of what they built. Never use them for general "
    "programming questions unrelated to their repos, and never claim to be able to change "
    "anything in GitHub — you cannot."
)


async def handle_agent_chat(
    message: str,
    retriever: Any,
    llm: Any,
    user_id: str,
    session_id: Optional[str] = None,
    allowed_document_ids: Optional[FrozenSet[str]] = None,
    node_postprocessors: Optional[list] = None,
) -> AsyncGenerator[str, None]:
    """
    Agent-mode counterpart to handle_streaming_chat: the same session handling and the same
    session/token/sources/[DONE] SSE contract, plus tool_call/tool_result events around each tool
    use. Only the final user and assistant text is persisted to session history; tool activity is
    replayed each turn from a fresh retrieval, not carried forward as saved state.
    """
    active_session_id, memory = get_or_create_session(user_id, session_id)

    document_titles = [document["filename"] for document in document_registry.list_documents(user_id)]
    tools, sources = build_document_tools(retriever, document_titles, allowed_document_ids, node_postprocessors)
    tools = tools + await build_github_tools(github_credentials.get_token(user_id))
    agent = FunctionAgent(tools=tools, llm=llm, system_prompt=SYSTEM_PROMPT)

    yield f"data: {json.dumps({'type': 'session', 'session_id': active_session_id})}\n\n"

    handler = agent.run(user_msg=message, chat_history=memory.get_all())

    full_answer = ""
    async for event in handler.stream_events():
        if isinstance(event, AgentStream) and event.delta:
            full_answer += event.delta
            yield f"data: {json.dumps({'type': 'token', 'content': event.delta})}\n\n"
        elif isinstance(event, ToolCall):
            yield f"data: {json.dumps({'type': 'tool_call', 'name': event.tool_name, 'arguments': event.tool_kwargs})}\n\n"
        elif isinstance(event, ToolCallResult):
            yield f"data: {json.dumps({'type': 'tool_result', 'name': event.tool_name})}\n\n"

    result = await handler  # surfaces any exception raised during the run
    if not full_answer:
        full_answer = str(result)

    memory.put(ChatMessage(role=MessageRole.USER, content=message))
    memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=full_answer))
    save_session(user_id, active_session_id, memory)

    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
    yield "data: [DONE]\n\n"
