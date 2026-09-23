from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.auth import get_current_user
from src.rag.registry import github_credentials
from src.services.github_service import GitHubSyncError, InvalidGitHubToken, sync_github, validate_token


router = APIRouter(prefix="/api/skills", tags=["GitHub Skills"])
token_router = APIRouter(prefix="/api/github", tags=["GitHub Connection"])


class GitHubSyncRequest(BaseModel):
    github_username: str = Field(min_length=1)


@router.post("/sync/github")
def sync_github_skills(
    request: GitHubSyncRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    try:
        return sync_github(current_user["user_id"], request.github_username)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


class GitHubTokenRequest(BaseModel):
    token: str = Field(min_length=1)


@token_router.post("/token")
def connect_github_token(
    request: GitHubTokenRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Validates the token against GitHub before storing it, so a typo or an already-revoked
    token never sits in the database looking connected.
    """
    try:
        validate_token(request.token)
    except InvalidGitHubToken as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except GitHubSyncError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    github_credentials.save_token(current_user["user_id"], request.token)
    return {"connected": True}


@token_router.get("/token")
def github_token_status(current_user: Annotated[dict, Depends(get_current_user)]):
    return {"connected": github_credentials.has_token(current_user["user_id"])}


@token_router.delete("/token", status_code=204)
def disconnect_github_token(current_user: Annotated[dict, Depends(get_current_user)]):
    github_credentials.delete_token(current_user["user_id"])