"""Low-level SQLite persistence for student skills and achievements."""

from typing import Any, Dict, List, Optional

from src.rag.registry.database import get_db_connection


def _rows_as_dicts(cursor: Any) -> List[Dict[str, Any]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def init_db() -> None:
    with get_db_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS skills (
                student_id TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                skill_type TEXT NOT NULL DEFAULT 'taxonomy',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (student_id, skill_name)
            );
            CREATE TABLE IF NOT EXISTS skill_evidence (
                evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                skill_name TEXT NOT NULL,
                raw_term TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_ref TEXT NOT NULL,
                confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id, skill_name)
                    REFERENCES skills(student_id, skill_name)
                    ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS achievements (
                achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                awarded_at TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            "ALTER TABLE skills ADD COLUMN skill_type TEXT NOT NULL DEFAULT 'taxonomy'"
        ) if "skill_type" not in [column[1] for column in conn.execute("PRAGMA table_info(skills)").fetchall()] else None
        conn.execute(
            """
            DELETE FROM skill_evidence
            WHERE evidence_id NOT IN (
                SELECT MAX(evidence_id)
                FROM skill_evidence
                GROUP BY student_id, skill_name, source_type, source_ref
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_skill_evidence_source
            ON skill_evidence(student_id, skill_name, source_type, source_ref)
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO skills (student_id, skill_name)
            SELECT DISTINCT student_id, skill_name FROM skill_evidence
            """
        )
        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_skills_student_id ON skills(student_id);
            CREATE INDEX IF NOT EXISTS idx_skill_evidence_student_id ON skill_evidence(student_id);
            CREATE INDEX IF NOT EXISTS idx_skill_evidence_skill ON skill_evidence(student_id, skill_name);
            CREATE INDEX IF NOT EXISTS idx_achievements_student_id ON achievements(student_id);
            """
        )
        conn.commit()


def migrate_skill_types(taxonomy_names: set[str]) -> None:
        """Repair legacy quiz-only skills created before skill_type existed."""
        placeholders = ", ".join("?" for _ in taxonomy_names) or "''"
        with get_db_connection() as conn:
                conn.execute(
                        f"""
                        UPDATE skills
                        SET skill_type = 'study_topic', updated_at = CURRENT_TIMESTAMP
                        WHERE skill_type = 'taxonomy'
                            AND skill_name NOT IN ({placeholders})
                            AND EXISTS (
                                    SELECT 1 FROM skill_evidence evidence
                                    WHERE evidence.student_id = skills.student_id
                                        AND evidence.skill_name = skills.skill_name
                                        AND evidence.source_type = 'quiz'
                            )
                            AND NOT EXISTS (
                                    SELECT 1 FROM skill_evidence evidence
                                    WHERE evidence.student_id = skills.student_id
                                        AND evidence.skill_name = skills.skill_name
                                        AND evidence.source_type != 'quiz'
                            )
                        """,
                        tuple(taxonomy_names),
                )
                conn.commit()


def upsert_skill(student_id: str, skill_name: str, skill_type: str = "taxonomy") -> None:
    if skill_type not in {"taxonomy", "study_topic"}:
        raise ValueError("skill_type must be taxonomy or study_topic")
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO skills (student_id, skill_name, skill_type)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id, skill_name) DO UPDATE SET
                updated_at = CURRENT_TIMESTAMP,
                skill_type = CASE
                    WHEN skills.skill_type = 'taxonomy' THEN 'taxonomy'
                    ELSE excluded.skill_type
                END
            """,
            (student_id, skill_name, skill_type),
        )
        conn.commit()


def upsert_skill_evidence(
    student_id: str,
    skill_name: str,
    raw_term: str,
    source_type: str,
    source_ref: str,
    confidence: float,
) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO skill_evidence
                (student_id, skill_name, raw_term, source_type, source_ref, confidence)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id, skill_name, source_type, source_ref) DO UPDATE SET
                raw_term = excluded.raw_term,
                confidence = excluded.confidence,
                created_at = CURRENT_TIMESTAMP
            """,
            (student_id, skill_name, raw_term, source_type, source_ref, confidence),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT evidence_id FROM skill_evidence
            WHERE student_id = ? AND skill_name = ?
              AND source_type = ? AND source_ref = ?
            """,
            (student_id, skill_name, source_type, source_ref),
        ).fetchone()
        return int(row[0])


def list_skill_names_with_evidence() -> List[str]:
    """Every distinct skill name that at least one student has evidence for — the source for an
    admin-facing skill filter, so only skills that could ever actually match something are offered.
    """
    with get_db_connection() as conn:
        rows = conn.execute("SELECT DISTINCT skill_name FROM skill_evidence ORDER BY skill_name")
        return [row[0] for row in rows]


def match_students_by_skills(
    skill_names: List[str],
    match: str = "any",
    min_confidence: float = 0.0,
) -> Dict[str, List[Dict[str, Any]]]:
    """Which students have which of the given skills, at or above min_confidence.

    A student's confidence for a skill is the highest confidence across all of their evidence for
    it — the same figure their own skill graph shows (see skill_service.get_skill_graph), so an
    admin's filtered results agree with what a student sees about themselves.

    match="any": a student needs at least one of skill_names. match="all": every one of them.
    Returns {student_id: [{"skill_name": ..., "confidence": ...}, ...]}.
    """
    if match not in {"any", "all"}:
        raise ValueError("match must be 'any' or 'all'")
    if not skill_names:
        return {}
    placeholders = ",".join("?" for _ in skill_names)
    with get_db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT student_id, skill_name, MAX(confidence) AS confidence
            FROM skill_evidence
            WHERE skill_name IN ({placeholders})
            GROUP BY student_id, skill_name
            HAVING MAX(confidence) >= ?
            """,
            (*skill_names, min_confidence),
        ).fetchall()

    by_student: Dict[str, List[Dict[str, Any]]] = {}
    for student_id, skill_name, confidence in rows:
        by_student.setdefault(student_id, []).append({"skill_name": skill_name, "confidence": confidence})

    if match == "all":
        required = set(skill_names)
        by_student = {
            student_id: matched
            for student_id, matched in by_student.items()
            if {m["skill_name"] for m in matched} >= required
        }
    return by_student


def select_skills(student_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT student_id, skill_name, skill_type, created_at, updated_at
            FROM skills WHERE student_id = ? ORDER BY skill_name
            """,
            (student_id,),
        )
        return _rows_as_dicts(cursor)


def select_skill_evidence(student_id: str, skill_name: Optional[str] = None) -> List[Dict[str, Any]]:
    query = """
        SELECT evidence_id, student_id, skill_name, raw_term, source_type,
               source_ref, confidence, created_at
        FROM skill_evidence WHERE student_id = ?
    """
    params: list[Any] = [student_id]
    if skill_name is not None:
        query += " AND skill_name = ?"
        params.append(skill_name)
    query += " ORDER BY evidence_id"
    with get_db_connection() as conn:
        cursor = conn.execute(query, params)
        return _rows_as_dicts(cursor)


def insert_achievement(
    student_id: str,
    name: str,
    description: Optional[str] = None,
    awarded_at: Optional[str] = None,
    metadata_json: str = "{}",
) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO achievements
                (student_id, name, description, awarded_at, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (student_id, name, description, awarded_at, metadata_json),
        )
        conn.commit()
        return int(cursor.lastrowid)


def select_achievements(student_id: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT achievement_id, student_id, name, description, awarded_at,
                   metadata_json, created_at
            FROM achievements WHERE student_id = ? ORDER BY achievement_id
            """,
            (student_id,),
        )
        return _rows_as_dicts(cursor)


def get_achievements(student_id: str) -> List[Dict[str, Any]]:
    return select_achievements(student_id)


init_db()