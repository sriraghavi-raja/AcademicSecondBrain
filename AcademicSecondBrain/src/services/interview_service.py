"""Mock interview lifecycle using the existing SQLite ChatMemoryBuffer store."""

import json
from typing import Any

from llama_index.core.base.llms.types import ChatMessage, MessageRole
from src.rag.registry.sessions import get_or_create_typed_session, save_typed_session
from src.rag.synthesis.prompts import INTERVIEW_SYSTEM_PROMPT
from src.services.skill_service import get_skill_graph
from src.services.study_service import get_weak_topics


async def start_interview(student_id: str, target_role: str, mode: str, llm: Any) -> dict[str, Any]:
    if mode not in {"technical", "behavioral"}:
        raise ValueError("mode must be technical or behavioral")
    session_id, memory = get_or_create_typed_session(session_type="interview")
    graph = get_skill_graph(student_id)
    weak_topics = get_weak_topics(student_id)
    prompt = INTERVIEW_SYSTEM_PROMPT.format(mode=mode, target_role=target_role)
    prompt += f"\nStudent skills: {json.dumps(graph['skills'])}\nWeak topics: {json.dumps(weak_topics)}"
    response = await llm.acomplete(prompt)
    question = getattr(response, "text", str(response)).strip()
    memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=question))
    save_typed_session(session_id, memory, "interview")
    return {"session_id": session_id, "question": question, "mode": mode, "target_role": target_role}


async def continue_interview(session_id: str, answer: str, llm: Any) -> dict[str, Any]:
    session_id, memory = get_or_create_typed_session(session_id, "interview")
    memory.put(ChatMessage(role=MessageRole.USER, content=answer))
    response = await llm.acomplete(f"Continue this mock interview. Conversation: {memory.get_all()}\nCandidate answer: {answer}")
    question = getattr(response, "text", str(response)).strip()
    memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=question))
    save_typed_session(session_id, memory, "interview")
    return {"session_id": session_id, "question": question}


def end_interview(session_id: str) -> dict[str, Any]:
    _, memory = get_or_create_typed_session(session_id, "interview")
    messages = [{"role": message.role.value, "content": message.content} for message in memory.get_all()]
    return {"session_id": session_id, "summary": "Interview completed.", "messages": messages, "linked_skill_gaps": []}