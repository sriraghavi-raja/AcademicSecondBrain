"""Student career-readiness aggregation for the dashboard endpoint."""

import json
from collections import defaultdict
from typing import Any

from src.rag.registry.database import get_db_connection


def get_dashboard(student_id: str) -> dict[str, Any]:
    with get_db_connection() as conn:
        profile_cursor = conn.execute("SELECT * FROM student_profile WHERE student_id=?", (student_id,))
        profile_row = profile_cursor.fetchone()
        profile = dict(zip([column[0] for column in profile_cursor.description], profile_row)) if profile_row else None

        skills_cursor = conn.execute(
            """
            SELECT s.skill_name, s.skill_type, MAX(e.confidence) AS confidence,
                   COUNT(e.evidence_id) AS evidence_count, MAX(e.created_at) AS last_evidence_at
            FROM skills s LEFT JOIN skill_evidence e
              ON e.student_id=s.student_id AND e.skill_name=s.skill_name
            WHERE s.student_id=? GROUP BY s.skill_name, s.skill_type ORDER BY confidence DESC
            """, (student_id,))
        skills = [dict(zip([column[0] for column in skills_cursor.description], row)) for row in skills_cursor.fetchall()]
        evidence_cursor = conn.execute(
            """
            SELECT skill_name, confidence, created_at
            FROM skill_evidence WHERE student_id=? ORDER BY created_at, evidence_id
            """, (student_id,))
        confidence_trends = defaultdict(list)
        for skill_name, confidence, created_at in evidence_cursor.fetchall():
            confidence_trends[skill_name].append({"confidence": round(confidence or 0, 3), "recorded_at": created_at})

        attempts_cursor = conn.execute(
            """
            SELECT concept_tag, COUNT(*) AS attempts, AVG(correct) AS accuracy,
                   MAX(answered_at) AS last_answered_at
            FROM quiz_attempts WHERE student_id=? GROUP BY concept_tag
            ORDER BY accuracy ASC, last_answered_at DESC
            """, (student_id,))
        weak_topics = [dict(zip([column[0] for column in attempts_cursor.description], row)) for row in attempts_cursor.fetchall()]

        achievements_cursor = conn.execute(
            "SELECT name, description, awarded_at, metadata_json, created_at FROM achievements WHERE student_id=? ORDER BY COALESCE(awarded_at, created_at) DESC",
            (student_id,))
        achievements = [dict(zip([column[0] for column in achievements_cursor.description], row)) for row in achievements_cursor.fetchall()]

        projects_cursor = conn.execute("SELECT project_id, title, tech_stack, source_type, source_ref FROM projects WHERE student_id=? ORDER BY project_id", (student_id,))
        projects = [dict(zip([column[0] for column in projects_cursor.description], row)) for row in projects_cursor.fetchall()]

        runs_cursor = conn.execute("SELECT run_type, summary_json, created_at FROM career_runs WHERE student_id=? ORDER BY created_at DESC", (student_id,))
        latest_runs = {}
        for run_type, summary_json, created_at in runs_cursor.fetchall():
            if run_type not in latest_runs:
                latest_runs[run_type] = {"created_at": created_at, "summary": json.loads(summary_json)}

    for skill in skills:
        skill["confidence"] = round(skill["confidence"] or 0, 3)
        skill["confidence_trend"] = confidence_trends.get(skill["skill_name"], [])
    weak_topics = [{**topic, "accuracy": round(topic["accuracy"] or 0, 3)} for topic in weak_topics]
    return {
        "student_id": student_id,
        "profile": profile,
        "summary": {
            "skill_count": len([skill for skill in skills if skill["skill_type"] == "taxonomy"]),
            "study_topic_count": len([skill for skill in skills if skill["skill_type"] == "study_topic"]),
            "project_count": len(projects),
            "achievement_count": len(achievements),
            "weak_topic_count": len([topic for topic in weak_topics if topic["accuracy"] < 0.7]),
        },
        "skills": skills,
        "weak_topics": weak_topics,
        "achievements": achievements,
        "projects": projects,
        "last_runs": latest_runs,
    }