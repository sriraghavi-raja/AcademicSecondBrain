import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.api.auth import get_current_user
from src.services.study_service import build_study_plan, export_study_plan, generate_quiz, get_weak_topics, parse_syllabus, record_attempt


router = APIRouter(prefix="/api/study", tags=["Study"])


class QuizRequest(BaseModel):
    document_id: str = Field(min_length=1)
    num_questions: int = Field(default=5, ge=1, le=20)


class AttemptRequest(BaseModel):
    document_id: str = Field(min_length=1)
    concept_tag: str = Field(min_length=1)
    correct: bool


class SubmitAttemptsRequest(BaseModel):
    attempts: list[AttemptRequest] = Field(min_length=1)


class StudyPlanRequest(BaseModel):
    syllabus_id: str = Field(min_length=1)
    weak_topics: list[dict] | None = None


@router.post("/plan")
async def create_study_plan(
    data: StudyPlanRequest,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    try:
        await parse_syllabus(request.app.state.index, request.app.state.llm, current_user["user_id"], data.syllabus_id)
        return build_study_plan(current_user["user_id"], data.syllabus_id, data.weak_topics)
    except (ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/plan/{plan_id}/export")
def export_plan(plan_id: str):
    try:
        return Response(
            content=export_study_plan(plan_id),
            media_type="text/calendar",
            headers={"Content-Disposition": f'attachment; filename="study-plan-{plan_id}.ics"'},
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/quiz")
async def create_quiz(
    request_data: QuizRequest,
    request: Request,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    try:
        questions, errors = await generate_quiz(
            request.app.state.index,
            request.app.state.llm,
            current_user["user_id"],
            request_data.document_id,
            request_data.num_questions,
        )
        return {
            "document_id": request_data.document_id,
            "requested_count": request_data.num_questions,
            "generated_count": len(questions),
            "errors": errors,
            "questions": questions,
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/quiz/submit")
def submit_quiz(
    request_data: SubmitAttemptsRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    results = []
    errors = []
    for attempt in request_data.attempts:
        try:
            results.append(record_attempt(student_id=current_user["user_id"], **attempt.model_dump()))
        except ValueError as error:
            errors.append({"concept_tag": attempt.concept_tag, "error": str(error)})
    return {"results": results, "errors": errors}


@router.get("/weak-topics")
def weak_topics(
    threshold: float = 0.7,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
):
    try:
        student_id = current_user["user_id"]
        return {"student_id": student_id, "weak_topics": get_weak_topics(student_id, threshold)}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error