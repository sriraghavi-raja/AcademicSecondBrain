"""Session application services backed by the existing SQLite registry."""

from datetime import datetime
from typing import Any

from src.rag.registry.sessions import (
    delete_session,
    get_session_history,
    list_sessions,
)


class SessionService:
    def list_sessions(self) -> list[dict[str, Any]]:
        sessions = list_sessions()
        mapped_sessions = []
        for session in sessions:
            session_id = session["session_id"]
            history = get_session_history(session_id)
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

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        return [
            {
                "id": index + 1,
                "role": message["role"],
                "content": message["content"],
                "timestamp": datetime.utcnow().isoformat(),
            }
            for index, message in enumerate(get_session_history(session_id))
        ]

    def delete_session(self, session_id: str) -> dict[str, str]:
        delete_session(session_id)
        return {"message": "Session deleted"}