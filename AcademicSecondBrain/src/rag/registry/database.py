import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.getenv("SQLITE_DB_PATH", "./registry.db")

@contextmanager
def get_db_connection():
    """Provides a transactional scope around a series of operations."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initializes the SQLite tables for the session store."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Sessions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                session_type TEXT NOT NULL DEFAULT 'chat',
                created_at TEXT NOT NULL,
                memory_blob TEXT NOT NULL
            )
        ''')
        # Databases created before sessions were owned by users lack these columns.
        # Legacy rows keep a NULL user_id, so no user can reach them.
        columns = {column[1] for column in cursor.execute("PRAGMA table_info(sessions)").fetchall()}
        if "user_id" not in columns:
            cursor.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
        if "session_type" not in columns:
            cursor.execute("ALTER TABLE sessions ADD COLUMN session_type TEXT NOT NULL DEFAULT 'chat'")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_sessions_owner ON sessions(user_id, session_type, created_at)'
        )

        conn.commit()

# Run initialization upon import
init_db()