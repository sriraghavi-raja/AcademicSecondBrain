import unittest
from unittest.mock import Mock, patch

from src.rag.synthesis.document_scope import DocumentAccessError
from src.services.rag_service import RagService
from src.services.session_service import SessionService
from tests.support import IsolatedDatabaseTestCase


class RagServiceTests(unittest.IsolatedAsyncioTestCase):
    @patch("src.services.rag_service.session_exists", return_value=True)
    @patch("src.services.rag_service.handle_streaming_chat")
    async def test_engine_mode_delegates_without_changing_arguments(self, handle_chat, session_exists):
        expected_events = ["data: {\"type\":\"session\"}\n\n"]
        handle_chat.return_value = expected_events
        retriever_factory = Mock()
        retriever_factory.for_user.return_value = "retriever"
        service = RagService(retriever_factory, "llm", ["postprocessor"], chat_mode="engine")

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

    @patch("src.services.rag_service.session_exists", return_value=True)
    def test_chat_mode_defaults_to_agent(self, session_exists):
        self.assertEqual(RagService(Mock(), "llm", []).chat_mode, "agent")
        self.assertEqual(RagService(Mock(), "llm", [], chat_mode="engine").chat_mode, "engine")

    @patch("src.services.rag_service.validate_document_ids", return_value=None)
    @patch("src.services.rag_service.session_exists", return_value=True)
    @patch("src.services.rag_service.handle_agent_chat")
    async def test_agent_mode_delegates_with_the_validated_document_scope(
        self, handle_agent, session_exists, validate_ids
    ):
        expected_events = ["data: {\"type\":\"session\"}\n\n"]
        handle_agent.return_value = expected_events
        retriever_factory = Mock()
        retriever_factory.for_user.return_value = "retriever"
        service = RagService(retriever_factory, "llm", ["postprocessor"], chat_mode="agent")

        events = service.ask("user-1", "question", "session", "doc-1")

        self.assertIs(events, expected_events)
        validate_ids.assert_called_once_with("user-1", ["doc-1"])
        handle_agent.assert_called_once_with(
            message="question",
            retriever="retriever",
            llm="llm",
            user_id="user-1",
            session_id="session",
            allowed_document_ids=None,
            node_postprocessors=["postprocessor"],
        )



class RagServiceDocumentScopeTests(IsolatedDatabaseTestCase):
    """Uses the real document registry (via a temp database), not a mock, for this one check."""

    @patch("src.services.rag_service.session_exists", return_value=True)
    def test_agent_mode_rejects_a_document_the_caller_does_not_own_before_streaming_starts(
        self, session_exists
    ):
        service = RagService(Mock(), "llm", [], chat_mode="agent")

        with self.assertRaises(DocumentAccessError):
            service.ask("user-1", "question", None, "someone-elses-document")


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