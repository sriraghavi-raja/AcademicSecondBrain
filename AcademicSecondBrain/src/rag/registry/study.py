"""SQLite persistence for quiz attempts."""

from typing import Any, Dict, List, Optional

from src.rag.registry.database import get_db_connection


def _rows_as_dicts(cursor: Any) -> List[Dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _drop_unowned_syllabus_topics(conn: Any) -> None:
    """
    Syllabus topics used to be keyed by the document's filename alone, so any student could overwrite or read
    them. They are derived data (a plan request re-parses the syllabus every time), so the old table is
    dropped instead of guessing an owner for its rows.
    """
    columns = [column[1] for column in conn.execute("PRAGMA table_info(syllabus_topics)").fetchall()]
    if columns and "student_id" not in columns:
        conn.execute("DROP TABLE syllabus_topics")


def init_db() -> None:
    with get_db_connection() as conn:
        _drop_unowned_syllabus_topics(conn)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                concept_tag TEXT NOT NULL,
                correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
                answered_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS syllabus_topics (
                topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                syllabus_id TEXT NOT NULL,
                topic TEXT NOT NULL,
                date_or_week TEXT,
                weight REAL,
                UNIQUE(student_id, syllabus_id, topic, date_or_week)
            );
            CREATE TABLE IF NOT EXISTS study_plans (
                plan_id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                syllabus_id TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student_id ON quiz_attempts(student_id);
            CREATE INDEX IF NOT EXISTS idx_quiz_attempts_topic ON quiz_attempts(student_id, concept_tag);
            CREATE INDEX IF NOT EXISTS idx_syllabus_topics_owner ON syllabus_topics(student_id, syllabus_id);
            CREATE INDEX IF NOT EXISTS idx_study_plans_student_id ON study_plans(student_id);
            """
        )
        conn.commit()


def insert_quiz_attempt(student_id: str, document_id: str, concept_tag: str, correct: bool) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO quiz_attempts(student_id, document_id, concept_tag, correct, answered_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (student_id, document_id, concept_tag, int(correct)),
        )
        conn.commit()
        return int(cursor.lastrowid)


def select_quiz_attempts(student_id: str, concept_tag: Optional[str] = None) -> List[Dict[str, Any]]:
    query = "SELECT attempt_id, student_id, document_id, concept_tag, correct, answered_at FROM quiz_attempts WHERE student_id = ?"
    params: list[Any] = [student_id]
    if concept_tag:
        query += " AND concept_tag = ?"
        params.append(concept_tag)
    query += " ORDER BY answered_at, attempt_id"
    with get_db_connection() as conn:
        return _rows_as_dicts(conn.execute(query, params))


def replace_syllabus_topics(student_id: str, syllabus_id: str, topics: List[Dict[str, Any]]) -> None:
    with get_db_connection() as conn:
        conn.execute("DELETE FROM syllabus_topics WHERE student_id = ? AND syllabus_id = ?", (student_id, syllabus_id))
        conn.executemany(
            "INSERT INTO syllabus_topics(student_id, syllabus_id, topic, date_or_week, weight) VALUES (?, ?, ?, ?, ?)",
            [(student_id, syllabus_id, topic["topic"], topic.get("date_or_week"), topic.get("weight")) for topic in topics],
        )
        conn.commit()


def select_syllabus_topics(student_id: str, syllabus_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        return _rows_as_dicts(conn.execute(
            "SELECT topic_id, student_id, syllabus_id, topic, date_or_week, weight FROM syllabus_topics "
            "WHERE student_id=? AND syllabus_id=? ORDER BY topic_id",
            (student_id, syllabus_id),
        ))


def insert_study_plan(plan_id: str, student_id: str, syllabus_id: str, plan_json: str) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO study_plans(plan_id, student_id, syllabus_id, plan_json) VALUES (?, ?, ?, ?)",
            (plan_id, student_id, syllabus_id, plan_json),
        )
        conn.commit()


def select_study_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM study_plans WHERE plan_id=?", (plan_id,))
        rows = _rows_as_dicts(cursor)
    return rows[0] if rows else None


init_db()