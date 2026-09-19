import inspect
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.api import documents as documents_api
from src.api import documents_router
from src.api.auth import get_current_user
from src.rag.ingestion import ingester
from src.rag.registry import documents as document_registry
from src.services.auth_service import AuthService
from tests.support import ORCHID, QUARTZ, IndexedTestCase, article


def status_of(call):
    """The HTTP status of the HTTPException that call() is expected to raise."""
    try:
        call()
    except HTTPException as error:
        return error.status_code
    raise AssertionError("expected an HTTPException")


class UploadStorageTests(IndexedTestCase):
    def test_files_are_stored_under_owner_and_file_id_with_a_neutral_name(self):
        result = self.upload("alice", "My Notes (final).txt", article(ORCHID))

        stored = Path(self.upload_dir, "alice", result["document_id"], "document.txt")
        self.assertEqual(self.stored_files(), [stored])
        self.assertTrue(stored.is_file())
        self.assertEqual(result["filename"], "My Notes (final).txt")

    def test_path_traversal_filenames_stay_inside_the_upload_folder(self):
        expected = {
            "../../escaped.txt": "escaped.txt",
            "..\\..\\escaped2.txt": "escaped2.txt",
            "/etc/passwd.txt": "passwd.txt",
            "C:\\Windows\\evil.txt": "evil.txt",
        }
        for number, name in enumerate(expected):
            self.upload("alice", name, article(ORCHID) + f" variant {number}")

        self.assertEqual(sorted(self.filenames("alice")), sorted(expected.values()))
        self.assertEqual(
            [path for path in self.workspace_root.rglob("*.txt") if Path(self.upload_dir) not in path.parents], []
        )
        for stored in self.stored_files():
            self.assertEqual(stored.parent.parent.parent, Path(self.upload_dir))

    def test_unicode_filenames_are_kept_for_display(self):
        self.upload("alice", "résumé notes.txt", article(ORCHID))

        self.assertEqual(self.filenames("alice"), ["résumé notes.txt"])

    def test_unsupported_file_types_are_rejected_and_leave_nothing(self):
        for name in ("virus.exe", "archive.zip", "noextension", "photo.png", "old.doc"):
            self.assertEqual(status_of(lambda: self.upload("alice", name, "content")), 415, name)

        self.assertEqual(self.documents.list_documents("alice"), [])
        self.assertEqual(self.stored_files(), [])

    def test_empty_and_nameless_uploads_are_rejected(self):
        self.assertEqual(status_of(lambda: self.upload("alice", "empty.txt", "")), 400)
        self.assertEqual(status_of(lambda: self.documents.ingest_document("alice", io.BytesIO(b"x"), None)), 400)
        self.assertEqual(status_of(lambda: self.documents.ingest_document("alice", io.BytesIO(b"x"), "..")), 400)

        self.assertEqual(self.stored_files(), [])

    def test_oversized_uploads_are_rejected_and_cleaned_up(self):
        self.documents.max_upload_bytes = 1000

        self.assertEqual(status_of(lambda: self.upload("alice", "big.txt", "x" * 5000)), 413)

        self.assertEqual(self.stored_files(), [])
        self.assertEqual(self.documents.list_documents("alice"), [])
        self.upload("alice", "small.txt", "y" * 900 + " " + "z" * 50)
        self.assertEqual(self.filenames("alice"), ["small.txt"])

    def test_the_same_content_twice_is_a_409_for_that_user_only(self):
        first = self.upload("alice", "a.txt", article(ORCHID))

        self.assertEqual(status_of(lambda: self.upload("alice", "copy.txt", article(ORCHID))), 409)
        self.assertEqual(self.filenames("alice"), ["a.txt"])
        self.assertEqual(len(self.stored_files()), 1)
        self.upload("bob", "a.txt", article(ORCHID))
        self.documents.delete_document("alice", first["document_id"])
        self.upload("alice", "again.txt", article(ORCHID))
        self.assertEqual(self.filenames("alice"), ["again.txt"])

    def test_the_same_filename_with_different_content_makes_two_independent_documents(self):
        first = self.upload("alice", "notes.txt", article(ORCHID))
        second = self.upload("alice", "notes.txt", article(QUARTZ))

        self.assertNotEqual(first["document_id"], second["document_id"])
        self.assertEqual(self.filenames("alice"), ["notes.txt", "notes.txt"])
        self.documents.delete_document("alice", first["document_id"])
        self.assertEqual(self.filenames("alice"), ["notes.txt"])
        self.assertTrue(any(QUARTZ in node.node.get_content() for node in self.retrieve("alice", QUARTZ)))
        self.assertFalse(any(ORCHID in node.node.get_content() for node in self.retrieve("alice", ORCHID)))

    def test_listing_reports_real_chunk_counts_and_upload_times(self):
        result = self.upload("alice", "a.txt", article(ORCHID))

        listed = self.documents.list_documents("alice")[0]

        leaves = [
            node
            for node in self.index.docstore.docs.values()
            if node.metadata.get("file_id") == result["document_id"] and not node.child_nodes
        ]
        self.assertGreater(len(leaves), 1)
        self.assertEqual(listed["chunk_count"], len(leaves))
        self.assertEqual(listed["chunk_count"], result["metadata"]["added_leaf_nodes"])
        self.assertNotEqual(listed["ingested_at"], "unknown")
        self.assertEqual(set(listed), {"document_id", "filename", "chunk_count", "ingested_at"})


class FailureHandlingTests(IndexedTestCase):
    def test_failed_ingestion_leaves_nothing_behind(self):
        with patch.object(self.index, "insert_nodes", side_effect=RuntimeError("embedding server down")):
            with self.assertRaises(RuntimeError):
                self.upload("alice", "a.txt", article(ORCHID))

        self.assertEqual(self.documents.list_documents("alice"), [])
        self.assertEqual(document_registry.list_processing(), [])
        self.assertEqual(len(self.index.docstore.docs), 0)
        self.assertEqual(self.index.vector_store.client.count(), 0)
        self.assertEqual(self.stored_files(), [])
        self.assertEqual({p for p in Path(self.upload_dir).rglob("*")}, {Path(self.upload_dir, "alice")})
        self.assertEqual(self.retrieve("alice", ORCHID), [])
        self.upload("alice", "a.txt", article(ORCHID))
        self.assertEqual(self.filenames("alice"), ["a.txt"])

    def test_interrupted_uploads_are_cleaned_up_at_startup(self):
        self.upload("alice", "ready.txt", article(QUARTZ))
        crashed_dir = Path(self.upload_dir, "alice", "crashed")
        crashed_dir.mkdir(parents=True)
        crashed_file = crashed_dir / "document.txt"
        crashed_file.write_text(article(ORCHID))
        document_registry.create_document("crashed", "alice", "crashed.txt", str(crashed_file), "hash-crashed", 10)
        ingester.ingest_new_documents(
            [str(crashed_file)], self.index, "alice", "crashed", "crashed.txt", persist_dir=self.persist_dir
        )
        self.assertEqual(self.filenames("alice"), ["ready.txt"])

        self.assertEqual(self.documents.recover_interrupted_uploads(), 1)

        self.assertFalse(crashed_dir.exists())
        self.assertEqual(document_registry.list_processing(), [])
        self.assertFalse(any(node.metadata.get("file_id") == "crashed" for node in self.index.docstore.docs.values()))
        self.assertEqual(self.filenames("alice"), ["ready.txt"])
        self.assertFalse(any(ORCHID in node.node.get_content() for node in self.retrieve("alice", ORCHID)))
        self.assertTrue(any(QUARTZ in node.node.get_content() for node in self.retrieve("alice", QUARTZ)))


class DeleteTests(IndexedTestCase):
    def test_delete_removes_the_files_the_row_the_vectors_and_the_nodes(self):
        document_id = self.upload("alice", "a.txt", article(ORCHID))["document_id"]

        self.documents.delete_document("alice", document_id)

        self.assertEqual(self.stored_files(), [])
        self.assertFalse(Path(self.upload_dir, "alice", document_id).exists())
        self.assertIsNone(document_registry.get_document("alice", document_id))
        self.assertEqual(self.index.vector_store.client.count(), 0)
        self.assertEqual(len(self.index.docstore.docs), 0)

    def test_deleting_an_unknown_or_foreign_id_is_a_404_and_changes_nothing(self):
        document_id = self.upload("alice", "a.txt", article(ORCHID))["document_id"]

        self.assertEqual(status_of(lambda: self.documents.delete_document("bob", document_id)), 404)
        self.assertEqual(status_of(lambda: self.documents.delete_document("alice", "no-such-id")), 404)

        self.assertEqual(self.filenames("alice"), ["a.txt"])
        self.assertEqual(len(self.stored_files()), 1)
        self.assertTrue(self.retrieve("alice", ORCHID))

    def test_a_document_id_is_not_a_filename(self):
        self.upload("alice", "a.txt", article(ORCHID))

        self.assertEqual(status_of(lambda: self.documents.delete_document("alice", "a.txt")), 404)


class DocumentApiTests(IndexedTestCase):
    def setUp(self):
        super().setUp()
        app = FastAPI()
        app.include_router(documents_router, dependencies=[Depends(get_current_user)])
        auth = AuthService("k" * 32)
        app.state.auth_service = auth
        app.state.document_service = self.documents
        self.client = TestClient(app)
        tokens = auth.signup("alice", "alice@example.org", "password-123", "College", "2026")
        self.headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    def post(self, name, content):
        return self.client.post("/api/docs/upload", files={"file": (name, content)}, headers=self.headers)

    def test_upload_and_list_use_the_documented_shapes_without_server_paths(self):
        uploaded = self.post("notes.txt", article(ORCHID).encode())

        self.assertEqual(uploaded.status_code, 200)
        body = uploaded.json()
        self.assertEqual(set(body), {"message", "document_id", "filename", "metadata"})
        self.assertEqual(set(body["metadata"]), {"added_total_nodes", "added_leaf_nodes"})
        listed = self.client.get("/api/docs", headers=self.headers).json()
        self.assertEqual(listed[0]["document_id"], body["document_id"])
        self.assertNotIn("file_path", listed[0])

    def test_validation_errors_use_meaningful_status_codes(self):
        self.post("a.txt", article(ORCHID).encode())

        self.assertEqual(self.post("a-copy.txt", article(ORCHID).encode()).status_code, 409)
        self.assertEqual(self.post("virus.exe", b"MZ").status_code, 415)
        self.assertEqual(self.post("empty.txt", b"").status_code, 400)
        self.documents.max_upload_bytes = 100
        self.assertEqual(self.post("big.txt", b"x" * 500).status_code, 413)

    def test_the_upload_endpoint_does_not_block_the_event_loop(self):
        self.assertFalse(inspect.iscoroutinefunction(documents_api.upload_document_endpoint))


if __name__ == "__main__":
    unittest.main()
