import io
import unittest
from unittest.mock import Mock, patch

from src.services.document_service import DocumentService
from src.services.rag_service import RagService
from src.services.session_service import SessionService


class RagServiceTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.services.rag_service.handle_streaming_chat")
    async def test_ask_delegates_without_changing_arguments(self, handle_chat):
        expected_events = ["data: {\"type\":\"session\"}\n\n"]
        handle_chat.return_value = expected_events
        service = RagService("retriever", "llm", ["postprocessor"])

        events = service.ask("question", "session", "document")

        self.assertIs(events, expected_events)
        handle_chat.assert_called_once_with(
            message="question",
            retriever="retriever",
            llm="llm",
            session_id="session",
            node_postprocessors=["postprocessor"],
        )


class DocumentServiceTests(unittest.TestCase):
    def setUp(self):
        self.index = Mock()
        self.retriever = Mock()
        self.service = DocumentService(self.index, self.retriever, "uploads")

    @patch("src.services.document_service.list_documents")
    def test_list_documents_preserves_api_mapping(self, list_documents):
        list_documents.return_value = [
            {"file_name": "paper.pdf", "file_path": "uploads/paper.pdf", "part_ids": ["a", "b"]}
        ]

        self.assertEqual(
            self.service.list_documents(),
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

    @patch("src.services.document_service.ingest_new_documents")
    def test_ingest_updates_bm25_and_returns_existing_response(self, ingest):
        ingest.return_value = {
            "added_total_nodes": 3,
            "added_leaf_nodes": 2,
            "bm25_retriever": "new-bm25",
        }

        with patch("builtins.open", unittest.mock.mock_open()) as open_file:
            result = self.service.ingest_document(io.BytesIO(b"data"), "paper.pdf")

        self.retriever.update_bm25.assert_called_once_with("new-bm25")
        self.assertEqual(result["message"], "Document ingested successfully")
        self.assertEqual(result["document_id"], "paper.pdf")
        self.assertEqual(result["metadata"]["added_total_nodes"], 3)
        open_file.assert_called_once()

    @patch("src.services.document_service.delete_document")
    def test_delete_preserves_response_and_retriever_argument(self, delete):
        delete.return_value = {"status": "success"}

        result = self.service.delete_document("paper.pdf")

        delete.assert_called_once_with(
            file_name="paper.pdf",
            index=self.index,
            retriever_wrapper=self.retriever,
        )
        self.assertEqual(result, {"message": "Document paper.pdf deleted"})


class SessionServiceTests(unittest.TestCase):
    @patch("src.services.session_service.get_session_history")
    @patch("src.services.session_service.list_sessions")
    def test_list_sessions_preserves_titles(self, list_sessions, get_history):
        list_sessions.return_value = [{"session_id": "abcd-1234", "created_at": "created"}]
        get_history.return_value = [{"role": "user", "content": "one two three"}]

        self.assertEqual(
            SessionService().list_sessions(),
            [{"id": "abcd-1234", "title": "one two three", "created_at": "created"}],
        )

    @patch("src.services.session_service.get_session_history")
    def test_get_history_maps_messages(self, get_history):
        get_history.return_value = [{"role": "user", "content": "hello"}]

        result = SessionService().get_history("session")

        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[0]["role"], "user")
        self.assertEqual(result[0]["content"], "hello")
        self.assertIn("timestamp", result[0])

    @patch("src.services.session_service.delete_session")
    def test_delete_session_preserves_response(self, delete):
        self.assertEqual(
            SessionService().delete_session("session"),
            {"message": "Session deleted"},
        )
        delete.assert_called_once_with("session")


if __name__ == "__main__":
    unittest.main()