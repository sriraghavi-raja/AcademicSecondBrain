"""Skill taxonomy matching and student skill graph orchestration."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.rag.registry.skills import (
    upsert_skill_evidence,
    select_achievements,
    select_skill_evidence,
    select_skills,
    upsert_skill,
    migrate_skill_types,
)


_TAXONOMY_PATH = Path(__file__).with_name("skill_taxonomy.json")
with _TAXONOMY_PATH.open(encoding="utf-8") as taxonomy_file:
    TAXONOMY = json.load(taxonomy_file)
migrate_skill_types(set(TAXONOMY.values()))


def merge_taxonomy_match(raw_term: str) -> Optional[str]:
    normalized = " ".join(raw_term.strip().lower().split())
    if not normalized:
        return None
    return TAXONOMY.get(normalized)


def add_evidence(
    student_id: str,
    raw_term: str,
    source_type: str,
    source_ref: str,
    confidence: float,
) -> Dict[str, Any]:
    skill_name = merge_taxonomy_match(raw_term)
    if skill_name is None:
        raise ValueError(f"Unknown skill term: {raw_term}")
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")

    upsert_skill(student_id, skill_name, "taxonomy")
    evidence_id = upsert_skill_evidence(
        student_id, skill_name, raw_term, source_type, source_ref, confidence
    )
    return {
        "evidence_id": evidence_id,
        "student_id": student_id,
        "skill_name": skill_name,
        "raw_term": raw_term,
        "source_type": source_type,
        "source_ref": source_ref,
        "confidence": confidence,
    }


def get_skill_graph(student_id: str) -> Dict[str, Any]:
    evidence_by_skill: dict[str, list[dict[str, Any]]] = {}
    for evidence in select_skill_evidence(student_id):
        evidence_by_skill.setdefault(evidence["skill_name"], []).append(evidence)

    skills = []
    for skill in select_skills(student_id):
        skill_evidence = evidence_by_skill.get(skill["skill_name"], [])
        unique_evidence = []
        seen_sources = set()
        for evidence in skill_evidence:
            source_key = (evidence["source_type"], evidence["source_ref"])
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            unique_evidence.append(evidence)
        skills.append(
            {
                "skill_name": skill["skill_name"],
                "skill_type": skill["skill_type"],
                "confidence": max(
                    (evidence["confidence"] for evidence in unique_evidence),
                    default=0.0,
                ),
                "evidence": unique_evidence,
            }
        )

    return {
        "student_id": student_id,
        "skills": skills,
        "achievements": select_achievements(student_id),
    }