from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.auth import require_admin
from src.services.auth_service import AuthError, AuthService
from src.api.auth import get_auth_service


router = APIRouter(prefix="/api/admin", tags=["Admin"])


class RoleUpdateRequest(BaseModel):
    role: Literal["student", "admin"]


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
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    if current_admin["user_id"] == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An admin cannot delete their own account")
    try:
        service.delete_user(user_id)
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error