from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.auth import get_current_user
from src.services.github_service import sync_github


router = APIRouter(prefix="/api/skills", tags=["GitHub Skills"])


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