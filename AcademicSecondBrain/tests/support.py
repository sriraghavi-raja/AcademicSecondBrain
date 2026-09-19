"""Shared fixtures that keep tests away from the real SQLite files."""

import os
import tempfile
import unittest

from src.rag.registry import auth as auth_registry
from src.rag.registry import career, database, skills, study


class IsolatedDatabaseTestCase(unittest.TestCase):
    """Points the registry and auth databases at throwaway files for one test."""

    def setUp(self):
        super().setUp()
        self.original_registry_path = database.DB_PATH
        self.original_auth_path = auth_registry.DB_PATH
        self._temporary_files = []
        database.DB_PATH = self._temporary_database()
        auth_registry.DB_PATH = self._temporary_database()
        database.init_db()
        skills.init_db()
        study.init_db()
        career.init_db()
        auth_registry.init_db()

    def tearDown(self):
        database.DB_PATH = self.original_registry_path
        auth_registry.DB_PATH = self.original_auth_path
        for path in self._temporary_files:
            os.unlink(path)
        super().tearDown()

    def _temporary_database(self) -> str:
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        self._temporary_files.append(handle.name)
        return handle.name
