import uuid
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from llama_index.core.memory import ChatMemoryBuffer
from src.rag.registry.database import get_db_connection


class SessionNotFoundError(LookupError):
    """The session does not exist, belongs to another user, or has another type."""


def create_session(user_id: str, session_type: str = "chat") -> Tuple[str, ChatMemoryBuffer]:
    """Creates an empty session owned by user_id with a server-generated id."""
    session_id = str(uuid.uuid4())
    memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
    with get_db_connection() as conn:
        conn.execute(
            '''INSERT INTO sessions (session_id, user_id, session_type, created_at, memory_blob)
               VALUES (?, ?, ?, ?, ?)''',
            (session_id, user_id, session_type, datetime.utcnow().isoformat(), memory.to_json())
        )
        conn.commit()
    return session_id, memory


def _find_memory(user_id: str, session_id: str, session_type: str) -> Optional[ChatMemoryBuffer]:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT memory_blob FROM sessions WHERE session_id = ? AND user_id = ? AND session_type = ?",
            (session_id, user_id, session_type)
        ).fetchone()
    return ChatMemoryBuffer.from_json(row[0]) if row else None


def load_session(user_id: str, session_id: str, session_type: str = "chat") -> ChatMemoryBuffer:
    """Loads a session's memory, or raises SessionNotFoundError if user_id does not own it."""
    memory = _find_memory(user_id, session_id, session_type)
    if memory is None:
        raise SessionNotFoundError("Session not found")
    return memory


def get_or_create_session(
        user_id: str,
        session_id: Optional[str] = None,
        session_type: str = "chat"
) -> Tuple[str, ChatMemoryBuffer]:
    """Creates a new session, or loads the one the caller owns. Client-chosen ids are never created."""
    if not session_id:
        return create_session(user_id, session_type)
    return session_id, load_session(user_id, session_id, session_type)


def session_exists(user_id: str, session_id: str, session_type: str = "chat") -> bool:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ? AND user_id = ? AND session_type = ?",
            (session_id, user_id, session_type)
        ).fetchone()
    return row is not None


def save_session(user_id: str, session_id: str, memory: ChatMemoryBuffer, session_type: str = "chat") -> None:
    """Stores the latest memory into a session the caller owns."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "UPDATE sessions SET memory_blob = ? WHERE session_id = ? AND user_id = ? AND session_type = ?",
            (memory.to_json(), session_id, user_id, session_type)
        )
        conn.commit()
    if cursor.rowcount == 0:
        raise SessionNotFoundError("Session not found")


def get_session_history(user_id: str, session_id: str, session_type: str = "chat") -> Optional[List[Dict[str, str]]]:
    """Maps a session's messages to role/content dicts, or returns None if the caller does not own it."""
    memory = _find_memory(user_id, session_id, session_type)
    if memory is None:
        return None
    return [{"role": msg.role.value, "content": msg.content} for msg in memory.get_all()]


def delete_session(user_id: str, session_id: str, session_type: str = "chat") -> bool:
    """Deletes a session the caller owns. Returns False if there was nothing to delete."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM sessions WHERE session_id = ? AND user_id = ? AND session_type = ?",
            (session_id, user_id, session_type)
        )
        conn.commit()
    return cursor.rowcount > 0


def list_sessions(user_id: str, session_type: str = "chat") -> List[Dict[str, str]]:
    """Returns the caller's sessions of one type, newest first."""
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT session_id, created_at FROM sessions WHERE user_id = ? AND session_type = ? ORDER BY created_at DESC",
            (user_id, session_type)
        ).fetchall()

    return [{"session_id": row[0], "created_at": row[1]} for row in rows]
