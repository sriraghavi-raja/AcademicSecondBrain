from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.auth import get_current_user
from src.services.skill_service import add_evidence, get_skill_graph


router = APIRouter(prefix="/api/skills", tags=["Skills"])


class SkillEvidenceRequest(BaseModel):
    raw_term: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


@router.get("")
def get_skills(current_user: Annotated[dict, Depends(get_current_user)]):
    return get_skill_graph(current_user["user_id"])


@router.post("/evidence")
def post_skill_evidence(
    evidence: SkillEvidenceRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    try:
        return add_evidence(
            student_id=current_user["user_id"],
            raw_term=evidence.raw_term,
            source_type=evidence.source_type,
            source_ref=evidence.source_ref,
            confidence=evidence.confidence,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error