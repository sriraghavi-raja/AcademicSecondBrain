from src.api.chat import router as chat_router
from src.api.sessions import router as sessions_router
from src.api.documents import router as documents_router
from src.api.skills import router as skills_router
from src.api.github import router as github_router, token_router as github_token_router
from src.api.study import router as study_router
from src.api.career import dashboard_router, profile_router, router as career_router
from src.api.auth import router as auth_router
from src.api.admin import router as admin_router

__all__ = ["chat_router", "sessions_router", "documents_router", "skills_router", "github_router", "github_token_router", "study_router", "career_router", "profile_router", "dashboard_router", "auth_router", "admin_router"]