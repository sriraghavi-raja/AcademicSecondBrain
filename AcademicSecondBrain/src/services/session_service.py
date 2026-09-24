"""Session application services backed by the existing SQLite registry."""

from datetime import datetime
from typing import Any

from src.rag.registry.sessions import (
    SessionNotFoundError,
    delete_session,
    get_session_history,
    list_sessions,
)


class SessionService:
    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        sessions = list_sessions(user_id)
        mapped_sessions = []
        for session in sessions:
            session_id = session["session_id"]
            history = get_session_history(user_id, session_id) or []
            title = f"New Chat ({session_id[:4]})"
            for message in history:
                if message["role"] == "user":
                    words = message["content"].strip().split()
                    title = (
                        " ".join(words[:6]) + "..."
                        if len(words) > 6
                        else message["content"].strip()
                    )
                    break
            mapped_sessions.append(
                {
                    "id": session_id,
                    "title": title,
                    "created_at": session["created_at"],
                }
            )
        return mapped_sessions

    def get_history(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        history = get_session_history(user_id, session_id)
        if history is None:
            raise SessionNotFoundError("Session not found")
        return [
            {
                "id": index + 1,
                "role": message["role"],
                "content": message["content"],
                "timestamp": datetime.utcnow().isoformat(),
            }
            for index, message in enumerate(history)
        ]

    def delete_session(self, user_id: str, session_id: str) -> dict[str, str]:
        if not delete_session(user_id, session_id):
            raise SessionNotFoundError("Session not found")
        return {"message": "Session deleted"}
