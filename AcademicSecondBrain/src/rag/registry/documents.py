"""SQLite records of uploaded documents. The index holds the content; this table holds who owns it."""

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.rag.registry.database import get_db_connection


class DuplicateDocumentError(Exception):
    """The owner already has a document with the same content hash."""


def _rows_as_dicts(cursor: Any) -> List[Dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def init_db() -> None:
    with get_db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                file_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'ready')),
                chunk_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_owner_hash ON documents(owner_id, sha256);
            CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_id, created_at);
            """
        )
        conn.commit()


def create_document(
    file_id: str,
    owner_id: str,
    filename: str,
    stored_path: str,
    sha256: str,
    size_bytes: int,
) -> None:
    """Records an upload as 'processing'. Raises DuplicateDocumentError if the owner already has this content."""
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT INTO documents (file_id, owner_id, filename, stored_path, sha256, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (file_id, owner_id, filename, stored_path, sha256, size_bytes, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
    except sqlite3.IntegrityError as error:
        raise DuplicateDocumentError(sha256) from error


def mark_ready(file_id: str, chunk_count: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE documents SET status = 'ready', chunk_count = ? WHERE file_id = ?",
            (chunk_count, file_id),
        )
        conn.commit()


def get_document(owner_id: str, file_id: str) -> Optional[Dict[str, Any]]:
    """The owner's document in any status, or None if it does not exist or belongs to someone else."""
    with get_db_connection() as conn:
        rows = _rows_as_dicts(
            conn.execute("SELECT * FROM documents WHERE owner_id = ? AND file_id = ?", (owner_id, file_id))
        )
    return rows[0] if rows else None


def find_by_hash(owner_id: str, sha256: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        rows = _rows_as_dicts(
            conn.execute("SELECT * FROM documents WHERE owner_id = ? AND sha256 = ?", (owner_id, sha256))
        )
    return rows[0] if rows else None


def list_documents(owner_id: str) -> List[Dict[str, Any]]:
    """The owner's fully indexed documents, oldest first."""
    with get_db_connection() as conn:
        return _rows_as_dicts(
            conn.execute(
                "SELECT * FROM documents WHERE owner_id = ? AND status = 'ready' ORDER BY created_at, file_id",
                (owner_id,),
            )
        )


def list_processing() -> List[Dict[str, Any]]:
    """Uploads that never finished, across all owners. Only meaningful at startup."""
    with get_db_connection() as conn:
        return _rows_as_dicts(conn.execute("SELECT * FROM documents WHERE status = 'processing'"))


def delete_document(owner_id: str, file_id: str) -> bool:
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM documents WHERE owner_id = ? AND file_id = ?", (owner_id, file_id))
        conn.commit()
    return cursor.rowcount > 0


def delete_all_for_owner(owner_id: str) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM documents WHERE owner_id = ?", (owner_id,))
        conn.commit()
    return cursor.rowcount


init_db()
