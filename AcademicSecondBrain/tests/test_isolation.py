import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.memory import ChatMemoryBuffer

from src.api import career_router, chat_router, sessions_router
from src.api.auth import get_current_user
from src.rag.registry import auth as auth_registry
from src.rag.registry import career, database
from src.rag.registry import sessions as session_registry
from src.rag.synthesis.chat import handle_streaming_chat
from src.services.auth_service import AuthService
from src.services.interview_service import continue_interview, start_interview
from src.services.rag_service import RagService
from src.services.session_service import SessionService
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


class FakeLLM:
    async def acomplete(self, prompt):
        return SimpleNamespace(text="Tell me about Python.")


class FakeStream:
    source_nodes = []

    async def async_response_gen(self):
        yield "ans"
        yield "wer"

    def __str__(self):
        return "answer"


class FakeChatEngine:
    def __init__(self, memory):
        self.memory = memory

    async def astream_chat(self, message):
        self.memory.put(ChatMessage(role=MessageRole.USER, content=message))
        self.memory.put(ChatMessage(role=MessageRole.ASSISTANT, content="answer"))
        return FakeStream()


class SessionRegistryIsolationTests(IsolatedDatabaseTestCase):
    def test_each_user_lists_only_their_own_sessions(self):
        alice_session, _ = session_registry.create_session("alice")
        bob_session, _ = session_registry.create_session("bob")

        self.assertEqual([s["session_id"] for s in session_registry.list_sessions("alice")], [alice_session])
        self.assertEqual([s["session_id"] for s in session_registry.list_sessions("bob")], [bob_session])
        self.assertEqual(session_registry.list_sessions("carol"), [])

    def test_history_is_hidden_from_other_users(self):
        session_id, _ = session_registry.create_session("alice")

        self.assertEqual(session_registry.get_session_history("alice", session_id), [])
        self.assertIsNone(session_registry.get_session_history("bob", session_id))

    def test_reading_an_unknown_session_creates_nothing(self):
        self.assertIsNone(session_registry.get_session_history("alice", "does-not-exist"))

        self.assertEqual(session_registry.list_sessions("alice"), [])

    def test_delete_only_removes_the_callers_own_session(self):
        session_id, _ = session_registry.create_session("alice")

        self.assertFalse(session_registry.delete_session("bob", session_id))
        self.assertEqual(len(session_registry.list_sessions("alice")), 1)
        self.assertTrue(session_registry.delete_session("alice", session_id))
        self.assertEqual(session_registry.list_sessions("alice"), [])

    def test_get_or_create_rejects_foreign_and_unknown_ids(self):
        session_id, _ = session_registry.create_session("alice")

        with self.assertRaises(session_registry.SessionNotFoundError):
            session_registry.get_or_create_session("bob", session_id)
        with self.assertRaises(session_registry.SessionNotFoundError):
            session_registry.get_or_create_session("alice", "client-chosen-id")
        same_id, _ = session_registry.get_or_create_session("alice", session_id)
        self.assertEqual(same_id, session_id)
        new_id, _ = session_registry.get_or_create_session("alice")
        self.assertNotEqual(new_id, session_id)

    def test_session_types_are_not_interchangeable(self):
        chat_id, _ = session_registry.create_session("alice", "chat")
        interview_id, _ = session_registry.create_session("alice", "interview")

        self.assertEqual([s["session_id"] for s in session_registry.list_sessions("alice")], [chat_id])
        self.assertEqual(
            [s["session_id"] for s in session_registry.list_sessions("alice", "interview")], [interview_id]
        )
        with self.assertRaises(session_registry.SessionNotFoundError):
            session_registry.get_or_create_session("alice", interview_id, "chat")
        with self.assertRaises(session_registry.SessionNotFoundError):
            session_registry.get_or_create_session("alice", chat_id, "interview")

    def test_save_cannot_write_into_someone_elses_session(self):
        session_id, memory = session_registry.create_session("alice")
        memory.put(ChatMessage(role=MessageRole.USER, content="mine"))

        with self.assertRaises(session_registry.SessionNotFoundError):
            session_registry.save_session("bob", session_id, memory)
        self.assertEqual(session_registry.get_session_history("alice", session_id), [])
        session_registry.save_session("alice", session_id, memory)
        self.assertEqual(session_registry.get_session_history("alice", session_id)[0]["content"], "mine")

    def test_legacy_table_is_migrated_and_legacy_rows_stay_private(self):
        with database.get_db_connection() as connection:
            connection.execute("DROP TABLE sessions")
            connection.execute(
                "CREATE TABLE sessions (session_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, memory_blob TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO sessions VALUES ('legacy', '2026-01-01T00:00:00', ?)",
                (ChatMemoryBuffer.from_defaults().to_json(),),
            )
            connection.commit()

        database.init_db()
        database.init_db()

        with database.get_db_connection() as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(sessions)")}
        self.assertTrue({"user_id", "session_type"} <= columns)
        self.assertEqual(session_registry.list_sessions("alice"), [])
        self.assertIsNone(session_registry.get_session_history("alice", "legacy"))

    def test_streaming_chat_creates_and_saves_the_session_for_the_caller(self):
        async def collect():
            return [
                event
                async for event in handle_streaming_chat(
                    message="hello", retriever=None, llm=None, user_id="alice", session_id=None, node_postprocessors=None
                )
            ]

        with patch("src.rag.synthesis.chat.CondensePlusContextChatEngine") as engine:
            engine.from_defaults.side_effect = lambda **kwargs: FakeChatEngine(kwargs["memory"])
            events = asyncio.run(collect())

        session_id = json.loads(events[0].removeprefix("data: "))["session_id"]
        self.assertEqual(events[-1], "data: [DONE]\n\n")
        self.assertEqual(
            [m["content"] for m in session_registry.get_session_history("alice", session_id)], ["hello", "answer"]
        )
        self.assertIsNone(session_registry.get_session_history("bob", session_id))

    def test_interview_cannot_continue_a_chat_session_or_someone_elses_interview(self):
        chat_id, _ = session_registry.create_session("alice", "chat")
        with patch("src.services.interview_service.get_skill_graph", return_value={"skills": []}), \
             patch("src.services.interview_service.get_weak_topics", return_value=[]):
            started = asyncio.run(start_interview("alice", "Developer", "technical", FakeLLM()))

        with self.assertRaises(session_registry.SessionNotFoundError):
            asyncio.run(continue_interview("alice", chat_id, "answer", FakeLLM()))
        with self.assertRaises(session_registry.SessionNotFoundError):
            asyncio.run(continue_interview("bob", started["session_id"], "answer", FakeLLM()))


class SessionServiceIsolationTests(IsolatedDatabaseTestCase):
    def test_history_and_delete_raise_not_found_for_other_users(self):
        session_id, _ = session_registry.create_session("alice")
        service = SessionService()

        with self.assertRaises(session_registry.SessionNotFoundError):
            service.get_history("bob", session_id)
        with self.assertRaises(session_registry.SessionNotFoundError):
            service.delete_session("bob", session_id)
        self.assertEqual(service.get_history("alice", session_id), [])
        self.assertEqual(service.delete_session("alice", session_id), {"message": "Session deleted"})


class SessionApiIsolationTests(IsolatedDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.app = FastAPI()
        protected = [Depends(get_current_user)]
        self.app.include_router(chat_router, dependencies=protected)
        self.app.include_router(sessions_router, dependencies=protected)
        self.app.include_router(career_router, dependencies=protected)
        self.auth = AuthService("k" * 32)
        self.app.state.auth_service = self.auth
        self.app.state.session_service = SessionService()
        self.app.state.llm = FakeLLM()
        self.app.state.rag_service = RagService(
            retriever_factory=Mock(), llm=None, postprocessors=None, chat_mode="engine"
        )
        self.client = TestClient(self.app)
        self.alice_id, self.alice = self._signup("alice")
        self.bob_id, self.bob = self._signup("bob")

    def _signup(self, name):
        tokens = self.auth.signup(name, f"{name}@example.org", "password-123", "College", "2026")
        return tokens["user"]["user_id"], {"Authorization": f"Bearer {tokens['access_token']}"}

    def test_requests_without_a_token_are_rejected(self):
        self.assertEqual(self.client.get("/api/chat/sessions").status_code, 401)

    def test_session_list_shows_only_the_callers_chats(self):
        alice_session, _ = session_registry.create_session(self.alice_id)
        session_registry.create_session(self.bob_id)

        alice_list = self.client.get("/api/chat/sessions", headers=self.alice).json()
        bob_list = self.client.get("/api/chat/sessions", headers=self.bob).json()

        self.assertEqual([s["id"] for s in alice_list], [alice_session])
        self.assertNotIn(alice_session, [s["id"] for s in bob_list])
        self.assertEqual(len(bob_list), 1)

    def test_history_of_another_users_session_is_404(self):
        session_id, _ = session_registry.create_session(self.alice_id)

        self.assertEqual(self.client.get(f"/api/chat/history/{session_id}", headers=self.alice).status_code, 200)
        self.assertEqual(self.client.get(f"/api/chat/history/{session_id}", headers=self.bob).status_code, 404)

    def test_history_of_an_unknown_session_is_404_and_creates_nothing(self):
        response = self.client.get("/api/chat/history/does-not-exist", headers=self.alice)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/api/chat/sessions", headers=self.alice).json(), [])

    def test_delete_of_another_users_session_is_404_and_keeps_it(self):
        session_id, _ = session_registry.create_session(self.alice_id)

        self.assertEqual(self.client.delete(f"/api/chat/session/{session_id}", headers=self.bob).status_code, 404)
        self.assertEqual(len(self.client.get("/api/chat/sessions", headers=self.alice).json()), 1)
        self.assertEqual(self.client.delete(f"/api/chat/session/{session_id}", headers=self.alice).status_code, 200)

    def test_chat_into_another_users_session_is_404_and_never_reaches_the_pipeline(self):
        session_id, _ = session_registry.create_session(self.alice_id)

        with patch("src.services.rag_service.handle_streaming_chat") as pipeline:
            response = self.client.post(
                "/chat", json={"question": "hi", "session_id": session_id}, headers=self.bob
            )

        self.assertEqual(response.status_code, 404)
        pipeline.assert_not_called()

    def test_chat_with_own_session_streams_and_passes_the_callers_id(self):
        session_id, _ = session_registry.create_session(self.alice_id)

        async def stream(**kwargs):
            yield 'data: {"type":"session"}\n\n'
            yield "data: [DONE]\n\n"

        with patch("src.services.rag_service.handle_streaming_chat", side_effect=lambda **kw: stream(**kw)) as pipeline:
            response = self.client.post(
                "/chat", json={"question": "hi", "session_id": session_id}, headers=self.alice
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("[DONE]", response.text)
        self.assertEqual(pipeline.call_args.kwargs["user_id"], self.alice_id)
        self.assertEqual(pipeline.call_args.kwargs["session_id"], session_id)

    def test_chat_without_a_pipeline_reports_503_not_500(self):
        self.app.state.rag_service = None

        response = self.client.post("/chat", json={"question": "hi"}, headers=self.alice)

        self.assertEqual(response.status_code, 503)

    def test_interview_sessions_are_private_and_not_listed_as_chats(self):
        started = self.client.post(
            "/api/career/interview/start",
            json={"target_role": "Developer", "mode": "technical"},
            headers=self.alice,
        )
        self.assertEqual(started.status_code, 200)
        interview_id = started.json()["session_id"]
        answer = {"session_id": interview_id, "answer": "An answer."}

        self.assertEqual(self.client.get("/api/chat/sessions", headers=self.alice).json(), [])
        self.assertEqual(self.client.post("/api/career/interview/continue", json=answer, headers=self.bob).status_code, 404)
        self.assertEqual(
            self.client.post("/api/career/interview/end", json={"session_id": interview_id}, headers=self.bob).status_code,
            404,
        )
        self.assertEqual(self.client.post("/api/career/interview/continue", json=answer, headers=self.alice).status_code, 200)
        self.assertEqual(
            self.client.post("/api/career/interview/end", json={"session_id": interview_id}, headers=self.alice).status_code,
            200,
        )


if __name__ == "__main__":
    unittest.main()
