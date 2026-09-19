"""Deletes every registry.db row a user owns: the database half of deleting an account."""

from typing import Dict, Tuple

from src.rag.registry.database import get_db_connection

# Every table that stores a user's data, with the column that holds the owner. The schema test in
# tests/test_account_deletion.py fails if a table with a student_id, owner_id or user_id column is
# missing from this list, so a new table cannot silently escape account deletion.
OWNED_TABLES: Tuple[Tuple[str, str], ...] = (
    ("skill_evidence", "student_id"),
    ("skills", "student_id"),
    ("achievements", "student_id"),
    ("quiz_attempts", "student_id"),
    ("syllabus_topics", "student_id"),
    ("study_plans", "student_id"),
    ("student_profile", "student_id"),
    ("projects", "student_id"),
    ("career_runs", "student_id"),
    ("documents", "owner_id"),
    ("sessions", "user_id"),
)


def delete_user_records(user_id: str) -> Dict[str, int]:
    """Deletes all of user_id's rows in one transaction and returns how many each table lost. Safe to repeat."""
    removed = {}
    with get_db_connection() as conn:
        for table, column in OWNED_TABLES:
            removed[table] = conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (user_id,)).rowcount
        conn.commit()
    return removed
