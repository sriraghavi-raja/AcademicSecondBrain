import tempfile
import unittest
from pathlib import Path

from src.rag.registry import auth as auth_registry
from src.rag.registry import career, database
from tests.support import IsolatedDatabaseTestCase


class DatabaseHarnessTests(IsolatedDatabaseTestCase):
    def test_databases_are_throwaway_files(self):
        temporary_directory = Path(tempfile.gettempdir()).resolve()
        for path in (database.DB_PATH, auth_registry.DB_PATH):
            self.assertEqual(Path(path).resolve().parent, temporary_directory)

    def test_writes_do_not_reach_the_real_registry(self):
        real_registry = Path(self.original_registry_path)
        before = real_registry.read_bytes() if real_registry.exists() else None

        career.record_career_run("student-x", "resume", {})

        after = real_registry.read_bytes() if real_registry.exists() else None
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
