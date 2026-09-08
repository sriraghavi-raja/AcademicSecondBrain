"""SQLite persistence for profile and resume project data."""

from typing import Any, Optional

from src.rag.registry.database import get_db_connection


def _rows(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def init_db() -> None:
    with get_db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS student_profile (
                student_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                location TEXT,
                college_name TEXT,
                degree TEXT,
                branch TEXT,
                college_start TEXT,
                college_end TEXT,
                cgpa TEXT,
                school_name TEXT,
                school_detail TEXT,
                school_dates TEXT,
                school_score TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS projects (
                project_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                title TEXT NOT NULL,
                tech_stack TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                description_text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(student_id, source_type, source_ref)
            );
            """
        )
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS career_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                run_type TEXT NOT NULL,
                summary_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_student_profile_student_id ON student_profile(student_id);
            CREATE INDEX IF NOT EXISTS idx_projects_student_id ON projects(student_id);
            CREATE INDEX IF NOT EXISTS idx_career_runs_student_id ON career_runs(student_id);
            CREATE INDEX IF NOT EXISTS idx_career_runs_type_created ON career_runs(student_id, run_type, created_at);
            """
        )
        conn.commit()


def upsert_profile(student_id: str, values: dict[str, Any]) -> dict[str, Any]:
    columns = [
        "full_name", "email", "phone", "location", "college_name", "degree", "branch",
        "college_start", "college_end", "cgpa", "school_name", "school_detail",
        "school_dates", "school_score",
    ]
    with get_db_connection() as conn:
        conn.execute(
            f"""
            INSERT INTO student_profile (student_id, {', '.join(columns)})
            VALUES (?, {', '.join('?' for _ in columns)})
            ON CONFLICT(student_id) DO UPDATE SET
            {', '.join(f'{column}=excluded.{column}' for column in columns)},
            updated_at=CURRENT_TIMESTAMP
            """,
            [student_id] + [values.get(column) for column in columns],
        )
        conn.commit()
        return get_profile(student_id)


def get_profile(student_id: str) -> Optional[dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM student_profile WHERE student_id = ?", (student_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))


def upsert_project(
    student_id: str,
    title: str,
    tech_stack: str,
    source_type: str,
    source_ref: str,
    description_text: str,
) -> dict[str, Any]:
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO projects(student_id, title, tech_stack, source_type, source_ref, description_text)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id, source_type, source_ref) DO UPDATE SET
                title=excluded.title,
                tech_stack=excluded.tech_stack,
                description_text=excluded.description_text
            """,
            (student_id, title, tech_stack, source_type, source_ref, description_text),
        )
        conn.commit()
        cursor = conn.execute(
            "SELECT * FROM projects WHERE student_id=? AND source_type=? AND source_ref=?",
            (student_id, source_type, source_ref),
        )
        return dict(zip([column[0] for column in cursor.description], cursor.fetchone()))


def get_projects(student_id: str) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        return _rows(conn.execute("SELECT * FROM projects WHERE student_id=? ORDER BY project_id", (student_id,)))


def record_career_run(student_id: str, run_type: str, summary: dict[str, Any]) -> None:
    import json

    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO career_runs(student_id, run_type, summary_json) VALUES (?, ?, ?)",
            (student_id, run_type, json.dumps(summary)),
        )
        conn.commit()


init_db()