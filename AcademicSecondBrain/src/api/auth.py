from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, model_validator

from src.services.auth_service import AuthError, AuthService


router = APIRouter(prefix="/api/auth", tags=["Auth"])
bearer_scheme = HTTPBearer(auto_error=False)


class SignupRequest(BaseModel):
    """Public self-signup. There is no role field: every account created here is a student.
    Admin accounts are created from the admin console instead (see src/api/admin.py).
    """

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    confirm_password: str = Field(min_length=8, max_length=72)
    college_name: str = Field(min_length=1, max_length=200)
    college_year: str = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def _auth_error(error: AuthError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    try:
        return service.user_from_access_token(credentials.credentials)
    except AuthError as error:
        raise _auth_error(error) from error


def require_admin(current_user: Annotated[dict, Depends(get_current_user)]) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return current_user


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(
    data: SignupRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
):
    try:
        return service.signup(
            data.name, str(data.email), data.password, data.college_name, data.college_year,
        )
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.post("/login")
def login(data: LoginRequest, service: Annotated[AuthService, Depends(get_auth_service)]):
    try:
        return service.login(data.email, data.password)
    except AuthError as error:
        raise _auth_error(error) from error


@router.post("/refresh")
def refresh(data: RefreshRequest, service: Annotated[AuthService, Depends(get_auth_service)]):
    try:
        return service.refresh(data.refresh_token)
    except AuthError as error:
        raise _auth_error(error) from error


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: RefreshRequest, service: Annotated[AuthService, Depends(get_auth_service)]):
    service.logout(data.refresh_token)


@router.get("/me")
def me(current_user: Annotated[dict, Depends(get_current_user)]):
    return current_user