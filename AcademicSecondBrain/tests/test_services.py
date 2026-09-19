import io
import os
import unittest
from unittest.mock import Mock, patch

from src.services.document_service import DocumentService
from src.services.rag_service import RagService
from src.services.session_service import SessionService


class RagServiceTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.services.rag_service.session_exists", return_value=True)
    @patch("src.services.rag_service.handle_streaming_chat")
    async def test_ask_delegates_without_changing_arguments(self, handle_chat, session_exists):
        expected_events = ["data: {\"type\":\"session\"}\n\n"]
        handle_chat.return_value = expected_events
        retriever_factory = Mock()
        retriever_factory.for_user.return_value = "retriever"
        service = RagService(retriever_factory, "llm", ["postprocessor"])

        events = service.ask("user-1", "question", "session", "document")

        self.assertIs(events, expected_events)
        session_exists.assert_called_once_with("user-1", "session")
        retriever_factory.for_user.assert_called_once_with("user-1")
        handle_chat.assert_called_once_with(
            message="question",
            retriever="retriever",
            llm="llm",
            user_id="user-1",
            session_id="session",
            node_postprocessors=["postprocessor"],
        )


class DocumentServiceTests(unittest.TestCase):
    def setUp(self):
        self.index = Mock()
        self.retriever_factory = Mock()
        self.service = DocumentService(self.index, self.retriever_factory, "uploads", persist_dir="persist")

    @patch("src.services.document_service.list_documents")
    def test_list_documents_preserves_api_mapping(self, list_documents):
        list_documents.return_value = [
            {"file_name": "paper.pdf", "file_path": "uploads/paper.pdf", "part_ids": ["a", "b"]}
        ]

        self.assertEqual(
            self.service.list_documents("user-1"),
            [
                {
                    "document_id": "paper.pdf",
                    "filename": "paper.pdf",
                    "file_path": "uploads/paper.pdf",
                    "chunk_count": 2,
                    "ingested_at": "unknown",
                }
            ],
        )

    @patch("src.services.document_service.os.makedirs")
    @patch("src.services.document_service.ingest_new_documents")
    def test_ingest_scopes_to_the_owner_and_returns_existing_response(self, ingest, makedirs):
        ingest.return_value = {
            "added_total_nodes": 3,
            "added_leaf_nodes": 2,
        }

        with patch("builtins.open", unittest.mock.mock_open()) as open_file:
            result = self.service.ingest_document("user-1", io.BytesIO(b"data"), "paper.pdf")

        ingest.assert_called_once_with(
            [os.path.join("uploads", "paper.pdf")], self.index, "user-1", persist_dir="persist"
        )
        self.retriever_factory.invalidate.assert_called_once_with("user-1")
        self.assertEqual(result["message"], "Document ingested successfully")
        self.assertEqual(result["document_id"], "paper.pdf")
        self.assertEqual(result["metadata"]["added_total_nodes"], 3)
        open_file.assert_called_once()

    @patch("src.services.document_service.delete_document")
    def test_delete_scopes_to_the_owner_and_refreshes_retrieval(self, delete):
        delete.return_value = {"status": "success"}

        result = self.service.delete_document("user-1", "paper.pdf")

        delete.assert_called_once_with(
            file_name="paper.pdf",
            index=self.index,
            owner_id="user-1",
            persist_dir="persist",
        )
        self.retriever_factory.invalidate.assert_called_once_with("user-1")
        self.assertEqual(result, {"message": "Document paper.pdf deleted"})


class SessionServiceTests(unittest.TestCase):
    @patch("src.services.session_service.get_session_history")
    @patch("src.services.session_service.list_sessions")
    def test_list_sessions_preserves_titles(self, list_sessions, get_history):
        list_sessions.return_value = [{"session_id": "abcd-1234", "created_at": "created"}]
        get_history.return_value = [{"role": "user", "content": "one two three"}]

        self.assertEqual(
            SessionService().list_sessions("user-1"),
            [{"id": "abcd-1234", "title": "one two three", "created_at": "created"}],
        )

    @patch("src.services.session_service.get_session_history")
    def test_get_history_maps_messages(self, get_history):
        get_history.return_value = [{"role": "user", "content": "hello"}]

        result = SessionService().get_history("user-1", "session")

        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "hello")
        self.assertIn("timestamp", result[0])

    @patch("src.services.session_service.delete_session", return_value=True)
    def test_delete_session_preserves_response(self, delete):
        self.assertEqual(
            SessionService().delete_session("user-1", "session"),
            {"message": "Session deleted"},
        )
        delete.assert_called_once_with("user-1", "session")


if __name__ == "__main__":
    unittest.main()