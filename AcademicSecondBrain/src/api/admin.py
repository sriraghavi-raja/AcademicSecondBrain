from typing import Annotated, List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field

from src.api.auth import require_admin
from src.rag.registry import skills as skill_registry
from src.services.account_service import AccountService
from src.services.auth_service import AuthError, AuthService
from src.api.auth import get_auth_service


router = APIRouter(prefix="/api/admin", tags=["Admin"])


def get_account_service(request: Request) -> AccountService:
    return request.app.state.account_service


class RoleUpdateRequest(BaseModel):
    role: Literal["student", "admin"]


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    college_name: str = Field(min_length=1, max_length=200)
    college_year: str = Field(min_length=1, max_length=20)
    role: Literal["student", "admin"] = "student"


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    data: CreateUserRequest,
    _: Annotated[dict, Depends(require_admin)],
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    """Only an admin can reach this, so unlike public signup, the role the caller asks for is
    trusted as-is. Returns the created user's profile only — never their access/refresh tokens.
    """
    try:
        result = service.signup(
            data.name, str(data.email), data.password, data.college_name, data.college_year, data.role,
        )
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return result["user"]


@router.get("/skills")
def list_skills(_: Annotated[dict, Depends(require_admin)]):
    """Every skill name at least one student has evidence for, for the search filter's options."""
    return {"skills": skill_registry.list_skill_names_with_evidence()}


@router.get("/students/by-skill")
def students_by_skill(
    _: Annotated[dict, Depends(require_admin)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    skill: Annotated[List[str], Query()] = [],
    match: Literal["any", "all"] = "any",
    min_confidence: float = 0.0,
):
    """Students who have the requested skill(s) at or above min_confidence."""
    if not 0 <= min_confidence <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="min_confidence must be between 0 and 1")
    if not skill:
        return {"students": []}

    matches = skill_registry.match_students_by_skills(skill, match=match, min_confidence=min_confidence)
    if not matches:
        return {"students": []}

    users_by_id = {user["user_id"]: user for user in auth_service.get_users_by_ids(list(matches.keys()))}
    students = [
        {**users_by_id[student_id], "matched_skills": sorted(matched, key=lambda m: m["skill_name"])}
        for student_id, matched in matches.items()
        if student_id in users_by_id  # defensive: a matched user could have been deleted since
    ]
    students.sort(key=lambda student: student["name"].lower())
    return {"students": students}


@router.get("/users")
def list_users(
    _: Annotated[dict, Depends(require_admin)],
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    return {"users": service.list_users()}


@router.get("/users/{user_id}")
def get_user(
    user_id: str,
    _: Annotated[dict, Depends(require_admin)],
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    user = service.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    data: RoleUpdateRequest,
    current_admin: Annotated[dict, Depends(require_admin)],
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    if current_admin["user_id"] == user_id and data.role != "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An admin cannot remove their own admin role")
    try:
        return service.update_role(user_id, data.role)
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    current_admin: Annotated[dict, Depends(require_admin)],
    accounts: Annotated[AccountService, Depends(get_account_service)],
):
    """Deletes the account and everything the user owns: documents, chats, skills, study and career records."""
    if current_admin["user_id"] == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An admin cannot delete their own account")
    try:
        accounts.delete_user(user_id)
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error