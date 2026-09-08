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
                created_at TEXT NOT NULL,
                memory_blob TEXT NOT NULL
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)')

        conn.commit()

# Run initialization upon import
init_db()