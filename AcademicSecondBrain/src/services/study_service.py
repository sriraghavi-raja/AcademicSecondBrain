"""Quiz generation, attempt recording, and weak-topic analysis."""

import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from ics import Calendar, Event

from src.rag.ingestion.metadata import FILE_KEY, OWNER_KEY
from src.rag.registry import documents as document_registry
from src.rag.registry.skills import upsert_skill, upsert_skill_evidence
from src.rag.registry.study import (
    insert_quiz_attempt,
    insert_study_plan,
    replace_syllabus_topics,
    select_quiz_attempts,
    select_study_plan,
    select_syllabus_topics,
)
from src.services.skill_service import merge_taxonomy_match


SYLLABUS_PARSE_PROMPT = """
Extract syllabus topics from the supplied text. Return JSON only:
{{"topics": [{{"topic": string, "date_or_week": string or null, "weight": number or null}}]}}
Keep topic names concise and preserve dates, weeks, and explicit weights exactly when present.
Text:
{syllabus_text}
"""


QUIZ_GENERATION_PROMPT = """
Create one academic multiple-choice question from the context below.
Return JSON only, with exactly these fields:
{{"question": string, "options": [string, string, string, string],
 "correct_option": integer from 0 to 3, "explanation": string,
 "concept_tag": string}}
Do not include markdown or extra fields.

Context:
{context}
"""


def _parse_quiz_item(raw_output: str) -> dict[str, Any]:
    candidate = raw_output.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    try:
        item = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise ValueError("Quiz model returned invalid JSON") from error

    required = {"question", "options", "correct_option", "explanation", "concept_tag"}
    if set(item) != required:
        raise ValueError("Quiz item has unexpected or missing fields")
    if not isinstance(item["question"], str) or not item["question"].strip():
        raise ValueError("Quiz question must be non-empty")
    options = item["options"]
    if not isinstance(options, list) or len(options) != 4:
        raise ValueError("Quiz item must have exactly four options")
    if any(not isinstance(option, str) or not option.strip() for option in options):
        raise ValueError("Quiz options must be non-empty strings")
    if len({option.strip().casefold() for option in options}) != 4:
        raise ValueError("Quiz options must be unique")
    if not isinstance(item["correct_option"], int) or not 0 <= item["correct_option"] <= 3:
        raise ValueError("correct_option must be an integer from 0 to 3")
    if not isinstance(item["explanation"], str) or not item["explanation"].strip():
        raise ValueError("Quiz explanation must be non-empty")
    if not isinstance(item["concept_tag"], str) or not item["concept_tag"].strip():
        raise ValueError("concept_tag must be non-empty")
    return item


def _canonicalize_concept_tag(concept_tag: str) -> tuple[str, str]:
    canonical = merge_taxonomy_match(concept_tag)
    if canonical:
        return canonical, "taxonomy"
    normalized = " ".join(concept_tag.strip().split())
    if not normalized:
        raise ValueError("concept_tag must be non-empty")
    return normalized.title(), "study_topic"


def _document_leaf_nodes(index: Any, owner_id: str, document_id: str) -> list[Any]:
    return [
        node
        for node in index.docstore.docs.values()
        if node.metadata.get(OWNER_KEY) == owner_id
        and node.metadata.get(FILE_KEY) == document_id
        and not node.child_nodes
    ]


async def generate_quiz(index: Any, llm: Any, owner_id: str, document_id: str, num_questions: int = 5) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not 1 <= num_questions <= 20:
        raise ValueError("num_questions must be between 1 and 20")
    nodes = _document_leaf_nodes(index, owner_id, document_id)
    if not nodes:
        raise ValueError(f"No leaf nodes found for document: {document_id}")

    questions = []
    errors = []
    for node in nodes[:num_questions]:
        try:
            response = await llm.acomplete(QUIZ_GENERATION_PROMPT.format(context=node.get_content()))
            text = getattr(response, "text", str(response))
            questions.append(_parse_quiz_item(text))
        except (ValueError, TypeError) as error:
            errors.append({"node_id": getattr(node, "node_id", None), "error": str(error)})
    return questions, errors


def record_attempt(student_id: str, document_id: str, concept_tag: str, correct: bool) -> dict[str, Any]:
    document = document_registry.get_document(student_id, document_id)
    if document is None or document["status"] != "ready":
        raise ValueError("Document not found")
    canonical_tag, skill_type = _canonicalize_concept_tag(concept_tag)
    upsert_skill(student_id, canonical_tag, skill_type)
    attempt_id = insert_quiz_attempt(student_id, document_id, canonical_tag, correct)
    attempts = select_quiz_attempts(student_id, canonical_tag)
    accuracy = sum(int(attempt["correct"]) for attempt in attempts) / len(attempts)
    upsert_skill_evidence(
        student_id, canonical_tag, concept_tag, "quiz", f"{document_id}:{canonical_tag}", accuracy
    )
    return {
        "attempt_id": attempt_id,
        "student_id": student_id,
        "document_id": document_id,
        "concept_tag": canonical_tag,
        "correct": correct,
        "accuracy": accuracy,
    }


def get_weak_topics(student_id: str, threshold: float = 0.7) -> list[dict[str, Any]]:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    attempts = select_quiz_attempts(student_id)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for attempt in attempts:
        grouped.setdefault(attempt["concept_tag"], []).append(attempt)
    weak_topics = []
    for concept_tag, concept_attempts in grouped.items():
        accuracy = sum(int(attempt["correct"]) for attempt in concept_attempts) / len(concept_attempts)
        if accuracy < threshold:
            weak_topics.append({
                "concept_tag": concept_tag,
                "accuracy": accuracy,
                "attempt_count": len(concept_attempts),
                "last_answered_at": concept_attempts[-1]["answered_at"],
            })
    return sorted(weak_topics, key=lambda topic: (topic["accuracy"], topic["last_answered_at"]))


def _syllabus_text(index: Any, owner_id: str, document_id: str) -> str:
    return "\n\n".join(node.get_content() for node in _document_leaf_nodes(index, owner_id, document_id))


async def parse_syllabus(index: Any, llm: Any, owner_id: str, document_id: str) -> dict[str, Any]:
    syllabus_text = _syllabus_text(index, owner_id, document_id)
    if not syllabus_text:
        raise ValueError(f"No syllabus content found for document: {document_id}")
    response = await llm.acomplete(SYLLABUS_PARSE_PROMPT.format(syllabus_text=syllabus_text))
    payload = json.loads(getattr(response, "text", str(response)))
    topics = payload.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError("Syllabus response must contain topics")
    cleaned = []
    for topic in topics:
        if not isinstance(topic, dict) or not isinstance(topic.get("topic"), str) or not topic["topic"].strip():
            raise ValueError("Each syllabus topic must contain a topic")
        cleaned.append({
            "topic": topic["topic"].strip(),
            "date_or_week": topic.get("date_or_week"),
            "weight": topic.get("weight"),
        })
    replace_syllabus_topics(owner_id, document_id, cleaned)
    return {"syllabus_id": document_id, "topics": cleaned}


def build_study_plan(student_id: str, syllabus_id: str, weak_topics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    topics = select_syllabus_topics(student_id, syllabus_id)
    if not topics:
        raise ValueError(f"No parsed syllabus found for: {syllabus_id}")
    weak_names = {topic["concept_tag"].casefold() for topic in (weak_topics or get_weak_topics(student_id))}
    sessions = []
    current_date = datetime.now().date()
    for index, topic in enumerate(topics):
        canonical = merge_taxonomy_match(topic["topic"]) or topic["topic"]
        repetitions = 2 if canonical.casefold() in weak_names or topic["topic"].casefold() in weak_names else 1
        for repetition in range(repetitions):
            session_date = current_date + timedelta(days=index * 2 + repetition)
            sessions.append({
                "date": session_date.isoformat(),
                "topic": canonical,
                "source_date_or_week": topic.get("date_or_week"),
                "session_type": "weak-topic-review" if repetitions > 1 else "syllabus-study",
            })
    plan_id = str(uuid.uuid4())
    plan = {"plan_id": plan_id, "student_id": student_id, "syllabus_id": syllabus_id, "sessions": sessions}
    insert_study_plan(plan_id, student_id, syllabus_id, json.dumps(plan))
    return plan


def export_study_plan(student_id: str, plan_id: str) -> str:
    stored = select_study_plan(plan_id)
    if not stored or stored["student_id"] != student_id:
        raise ValueError(f"Study plan not found: {plan_id}")
    plan = json.loads(stored["plan_json"])
    calendar = Calendar()
    for session in plan["sessions"]:
        event = Event()
        event.name = f"Study: {session['topic']}"
        event.begin = datetime.fromisoformat(session["date"])
        event.duration = timedelta(hours=1)
        event.description = f"{session['session_type']} for {plan['syllabus_id']}"
        calendar.events.add(event)
    return str(calendar)