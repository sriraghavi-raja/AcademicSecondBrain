"""Shared fixtures that keep tests away from the real SQLite files and the real index."""

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llama_index.core import Settings
from llama_index.core.embeddings import MockEmbedding

from src.rag.ingestion import indexer
from src.rag.registry import auth as auth_registry
from src.rag.registry import career, database, skills, study
from src.rag.registry import documents as document_registry
from src.rag.retrieval import retreiver
from src.services.document_service import DocumentService

ORCHID = "orchidalpha"
GRANITE = "granitebeta"
QUARTZ = "quartzgamma"


def article(token: str) -> str:
    """Long enough to be split into several levels of the node hierarchy."""
    return " ".join(f"Sentence {number} about {token} and other general study topics." for number in range(120))


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
        document_registry.init_db()
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


class IndexedTestCase(IsolatedDatabaseTestCase):
    """A real Chroma-backed index in a temp folder, embedded with a mock model (no LM Studio needed)."""

    def setUp(self):
        super().setUp()
        workspace = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(workspace.cleanup)
        embedding = patch.object(Settings, "_embed_model", MockEmbedding(embed_dim=8))
        embedding.start()
        self.addCleanup(embedding.stop)
        self.workspace_root = Path(workspace.name)
        self.chroma_path = str(self.workspace_root / "chroma")
        self.persist_dir = str(self.workspace_root / "storage")
        self.upload_dir = str(self.workspace_root / "uploads")
        self.index = indexer.load_or_create_index(db_path=self.chroma_path, persist_dir=self.persist_dir)
        self.factory = retreiver.RetrieverFactory(self.index)
        self.documents = DocumentService(
            self.index, self.factory, upload_dir=self.upload_dir, persist_dir=self.persist_dir
        )

    def upload(self, owner, filename, text):
        return self.documents.ingest_document(owner, io.BytesIO(text.encode()), filename)

    def retrieve(self, user, query):
        return self.factory.for_user(user).retrieve(query)

    def filenames(self, owner):
        return [document["filename"] for document in self.documents.list_documents(owner)]

    def stored_files(self):
        root = Path(self.upload_dir)
        return [path for path in root.rglob("*") if path.is_file()] if root.exists() else []
