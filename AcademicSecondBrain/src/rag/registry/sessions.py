import uuid
from typing import Tuple, List, Dict
from datetime import datetime
from llama_index.core.memory import ChatMemoryBuffer
from src.rag.registry.database import get_db_connection


def get_or_create_session(session_id: str = None) -> Tuple[str, ChatMemoryBuffer]:
    """Retrieves an existing session memory or initializes a new one."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        if session_id:
            cursor.execute("SELECT memory_blob FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                # Load existing buffer from stringified JSON
                memory = ChatMemoryBuffer.from_json(row[0])
                return session_id, memory

        # Generate new session if none exists or wasn't found
        new_session_id = session_id or str(uuid.uuid4())
        memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
        memory_blob = memory.to_json()

        cursor.execute(
            '''INSERT INTO sessions (session_id, created_at, memory_blob)
               VALUES (?, ?, ?)''',
            (new_session_id, datetime.utcnow().isoformat(), memory_blob)
        )
        conn.commit()

    return new_session_id, memory


def get_or_create_typed_session(session_id: str = None, session_type: str = "chat") -> Tuple[str, ChatMemoryBuffer]:
    """Reuse the existing memory store while tagging interview sessions separately."""
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                memory_blob TEXT NOT NULL
            )
            """
        )
        columns = [column[1] for column in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        if "session_type" not in columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN session_type TEXT NOT NULL DEFAULT 'chat'")
            conn.commit()
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_type ON sessions(session_type)")
        if session_id:
            row = conn.execute(
                "SELECT memory_blob FROM sessions WHERE session_id=? AND session_type=?",
                (session_id, session_type),
            ).fetchone()
            if row:
                return session_id, ChatMemoryBuffer.from_json(row[0])
        new_session_id = session_id or str(uuid.uuid4())
        memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
        conn.execute(
            "INSERT INTO sessions(session_id, created_at, memory_blob, session_type) VALUES (?, ?, ?, ?)",
            (new_session_id, datetime.utcnow().isoformat(), memory.to_json(), session_type),
        )
        conn.commit()
        return new_session_id, memory


def save_typed_session(session_id: str, memory: ChatMemoryBuffer, session_type: str = "chat") -> None:
    with get_db_connection() as conn:
        columns = [column[1] for column in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        if "session_type" not in columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN session_type TEXT NOT NULL DEFAULT 'chat'")
        conn.execute(
            "UPDATE sessions SET memory_blob=?, session_type=? WHERE session_id=?",
            (memory.to_json(), session_type, session_id),
        )
        conn.commit()


def save_session(session_id: str, memory: ChatMemoryBuffer) -> None:
    """Updates the session with the latest memory blob using a safe upsert."""
    memory_blob = memory.to_json()
    with get_db_connection() as conn:
        # INSERT OR REPLACE-safe upsert approach
        conn.execute(
            '''INSERT INTO sessions (session_id, created_at, memory_blob)
               VALUES (?, ?, ?) ON CONFLICT(session_id) DO
            UPDATE SET memory_blob = excluded.memory_blob''',
            (session_id, datetime.utcnow().isoformat(), memory_blob)
        )
        conn.commit()


def get_session_history(session_id: str) -> List[Dict[str, str]]:
    """Loads a session's buffer and maps its messages to role/content JSON."""
    _, memory = get_or_create_session(session_id)
    history = []

    for msg in memory.get_all():
        history.append({
            "role": msg.role.value,
            "content": msg.content
        })

    return history


def delete_session(session_id: str) -> None:
    """Deletes a session from the registry."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()


def list_sessions() -> List[Dict[str, str]]:
    """Returns a list of all active sessions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, created_at FROM sessions ORDER BY created_at DESC")
        rows = cursor.fetchall()

    return [{"session_id": row[0], "created_at": row[1]} for row in rows]