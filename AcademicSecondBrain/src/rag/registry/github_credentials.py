"""A student's own GitHub personal access token, one per user, encrypted at rest. Used to scope the
chat agent's GitHub MCP tools to that student's own repositories.
"""

from datetime import datetime, timezone
from typing import Optional

from src.rag.registry.database import get_db_connection
from src.rag.security.crypto import decrypt, encrypt


def init_db() -> None:
    with get_db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS github_credentials (
                user_id TEXT PRIMARY KEY,
                encrypted_token TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


def save_token(user_id: str, token: str) -> None:
    """Stores the user's GitHub token, replacing any previous one."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO github_credentials (user_id, encrypted_token, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                encrypted_token = excluded.encrypted_token,
                created_at = excluded.created_at
            """,
            (user_id, encrypt(token), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def get_token(user_id: str) -> Optional[str]:
    """The user's own decrypted GitHub token, or None if they haven't connected one."""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT encrypted_token FROM github_credentials WHERE user_id = ?", (user_id,)
        ).fetchone()
    return decrypt(row[0]) if row else None


def has_token(user_id: str) -> bool:
    with get_db_connection() as conn:
        row = conn.execute("SELECT 1 FROM github_credentials WHERE user_id = ?", (user_id,)).fetchone()
    return row is not None


def delete_token(user_id: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM github_credentials WHERE user_id = ?", (user_id,))
        conn.commit()
    return cursor.rowcount > 0


init_db()
