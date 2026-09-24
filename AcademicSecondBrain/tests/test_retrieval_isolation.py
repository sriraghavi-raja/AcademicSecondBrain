import shutil
import unittest
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from llama_index.core.schema import MetadataMode

from src.api import documents_router
from src.api.auth import get_current_user
from src.rag.ingestion import indexer
from src.services.auth_service import AuthService
from tests.support import GRANITE, ORCHID, QUARTZ, IndexedTestCase, article


class IndexLifecycleTests(IndexedTestCase):
    def test_first_start_creates_and_persists_an_empty_index(self):
        self.assertTrue(Path(self.persist_dir, "docstore.json").exists())
        self.assertEqual(self.index.vector_store.client.count(), 0)
        self.assertEqual(len(self.index.docstore.docs), 0)

    def test_persisted_index_is_reloaded_with_its_owners(self):
        self.upload("alice", "a.txt", article(ORCHID))

        reloaded = indexer.load_or_create_index(db_path=self.chroma_path, persist_dir=self.persist_dir)

        self.assertGreater(len(reloaded.docstore.docs), 0)
        self.assertEqual({node.metadata["owner_id"] for node in reloaded.docstore.docs.values()}, {"alice"})

    def test_vectors_without_a_docstore_is_refused_instead_of_served(self):
        self.upload("alice", "a.txt", article(ORCHID))
        shutil.rmtree(self.persist_dir)

        with self.assertRaises(RuntimeError):
            indexer.load_or_create_index(db_path=self.chroma_path, persist_dir=self.persist_dir)


class ScopedRetrievalTests(IndexedTestCase):
    def test_users_retrieve_only_their_own_documents(self):
        self.upload("alice", "alice.txt", article(ORCHID))
        self.upload("bob", "bob.txt", article(GRANITE))
        query = f"{ORCHID} {GRANITE}"

        for user, other_token in (("alice", GRANITE), ("bob", ORCHID)):
            nodes = self.retrieve(user, query)
            self.assertTrue(nodes)
            for node in nodes:
                self.assertEqual(node.node.metadata["owner_id"], user)
                self.assertNotIn(other_token, node.node.get_content())

    def test_a_user_without_documents_retrieves_nothing(self):
        self.upload("alice", "alice.txt", article(ORCHID))

        self.assertEqual(self.retrieve("carol", ORCHID), [])

    def test_bm25_is_built_from_only_the_users_nodes(self):
        self.upload("alice", "alice.txt", article(ORCHID))
        self.upload("bob", "bob.txt", article(GRANITE))

        hits = self.factory.bm25_for("alice").retrieve(GRANITE)

        self.assertTrue(all(hit.node.metadata["owner_id"] == "alice" for hit in hits))
        self.assertFalse(any(GRANITE in hit.node.get_content() for hit in hits))
        self.assertIsNone(self.factory.bm25_for("carol"))

    def test_bm25_sees_uploads_made_after_it_was_first_built(self):
        self.upload("alice", "one.txt", article(ORCHID))
        self.factory.bm25_for("alice")

        self.upload("alice", "two.txt", article(QUARTZ))

        hits = self.factory.bm25_for("alice").retrieve(QUARTZ)
        self.assertTrue(any(QUARTZ in hit.node.get_content() for hit in hits))


class DocumentOwnershipTests(IndexedTestCase):
    def test_each_user_lists_only_their_own_documents(self):
        self.upload("alice", "a.txt", article(ORCHID))
        self.upload("bob", "b.txt", article(GRANITE))

        self.assertEqual(self.filenames("alice"), ["a.txt"])
        self.assertEqual(self.filenames("bob"), ["b.txt"])
        self.assertEqual(self.filenames("carol"), [])

    def test_the_same_filename_for_two_users_stays_separate(self):
        alice_document = self.upload("alice", "notes.txt", article(ORCHID))["document_id"]
        bob_document = self.upload("bob", "notes.txt", article(GRANITE))["document_id"]
        self.assertNotEqual(alice_document, bob_document)

        self.documents.delete_document("alice", alice_document)

        self.assertEqual(self.filenames("alice"), [])
        self.assertEqual(self.filenames("bob"), ["notes.txt"])
        self.assertTrue(self.retrieve("bob", GRANITE))

    def test_deleting_someone_elses_document_is_a_404_and_changes_nothing(self):
        alice_document = self.upload("alice", "notes.txt", article(ORCHID))["document_id"]

        with self.assertRaises(HTTPException) as caught:
            self.documents.delete_document("bob", alice_document)

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(self.filenames("alice"), ["notes.txt"])
        self.assertTrue(self.retrieve("alice", ORCHID))

    def test_deleted_documents_leave_the_vectors_the_docstore_and_retrieval(self):
        document_id = self.upload("alice", "a.txt", article(ORCHID))["document_id"]
        self.assertGreater(self.index.vector_store.client.count(), 0)

        self.documents.delete_document("alice", document_id)

        self.assertEqual(self.index.vector_store.client.count(), 0)
        self.assertEqual(len(self.index.docstore.docs), 0)
        self.assertEqual(self.retrieve("alice", ORCHID), [])

    def test_nodes_carry_owner_file_id_and_original_name_but_prompts_do_not_show_bookkeeping(self):
        document_id = self.upload("alice", "My Notes.txt", article(ORCHID))["document_id"]

        nodes = list(self.index.docstore.docs.values())

        self.assertGreater(len(nodes), 1)
        for node in nodes:
            self.assertEqual(node.metadata["owner_id"], "alice")
            self.assertEqual(node.metadata["file_id"], document_id)
            self.assertEqual(node.metadata["file_name"], "My Notes.txt")
            for mode in (MetadataMode.EMBED, MetadataMode.LLM):
                text = node.get_content(metadata_mode=mode)
                self.assertNotIn("alice", text)
                self.assertNotIn(document_id, text)
                self.assertNotIn(self.upload_dir, text)


class DocumentApiOwnershipTests(IndexedTestCase):
    def setUp(self):
        super().setUp()
        self.app = FastAPI()
        self.app.include_router(documents_router, dependencies=[Depends(get_current_user)])
        self.auth = AuthService("k" * 32)
        self.app.state.auth_service = self.auth
        self.app.state.document_service = self.documents
        self.client = TestClient(self.app)
        self.alice = self._signup("alice")
        self.bob = self._signup("bob")

    def _signup(self, name):
        tokens = self.auth.signup(name, f"{name}@example.org", "password-123", "College", "2026")
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    def test_requests_without_a_token_are_rejected(self):
        self.assertEqual(self.client.get("/api/docs").status_code, 401)

    def test_upload_list_and_delete_are_private_to_the_caller(self):
        uploaded = self.client.post(
            "/api/docs/upload", files={"file": ("notes.txt", article(ORCHID).encode())}, headers=self.alice
        )
        self.assertEqual(uploaded.status_code, 200)
        document_id = uploaded.json()["document_id"]

        self.assertEqual([d["filename"] for d in self.client.get("/api/docs", headers=self.alice).json()], ["notes.txt"])
        self.assertEqual(self.client.get("/api/docs", headers=self.bob).json(), [])
        self.assertEqual(self.client.delete(f"/api/docs/{document_id}", headers=self.bob).status_code, 404)
        self.assertEqual(len(self.client.get("/api/docs", headers=self.alice).json()), 1)
        self.assertEqual(self.client.delete(f"/api/docs/{document_id}", headers=self.alice).status_code, 200)
        self.assertEqual(self.client.get("/api/docs", headers=self.alice).json(), [])


if __name__ == "__main__":
    unittest.main()
