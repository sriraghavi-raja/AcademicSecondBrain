"""Plumbing tests for agent-mode chat: session handling, SSE framing, and history persistence.

These patch FunctionAgent itself with a scripted fake (the same style tests/test_isolation.py uses
for CondensePlusContextChatEngine) so they stay fast and offline; the fake replays real event
objects (AgentStream/ToolCall/ToolCallResult), so the event-mapping code under test is exercised
against the library's real shapes. Whether Groq's model actually calls tools sensibly was checked
separately with a live request, not here.
"""

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from llama_index.core.agent.workflow import AgentStream, ToolCall, ToolCallResult
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.tools.types import ToolOutput

from src.api import chat_router
from src.api.auth import get_current_user
from src.rag.synthesis.agent_chat import handle_agent_chat
from src.rag.registry import github_credentials
from src.rag.registry import sessions as session_registry
from src.services.auth_service import AuthService
from src.services.rag_service import RagService
from tests.support import IsolatedDatabaseTestCase


def tool_call(name="search_documents", query="hi"):
    return ToolCall(tool_name=name, tool_kwargs={"query": query}, tool_id="call-1")


def tool_call_result(name="search_documents", output="found it"):
    return ToolCallResult(
        tool_name=name,
        tool_kwargs={"query": "hi"},
        tool_id="call-1",
        tool_output=ToolOutput(content=output, tool_name=name, raw_input={}, raw_output=output),
        return_direct=False,
    )


def stream(delta, response=""):
    return AgentStream(delta=delta, response=response or delta, current_agent_name="agent")


class FakeAgentHandler:
    def __init__(self, tools, events, result=""):
        self._tools = tools
        self._events = events
        self._result = result

    async def stream_events(self):
        for event in self._events:
            if isinstance(event, ToolCall) and self._tools:
                # Mirror what a real agent does: actually invoke the matching tool, so a scripted
                # ToolCall/ToolCallResult pair produces the tool's real side effects (e.g. the
                # `sources` list build_document_tools populates), not just replayed event shells.
                tool = next((t for t in self._tools if t.metadata.name == event.tool_name), None)
                if tool is not None:
                    tool.call(**event.tool_kwargs)
            yield event

    def __await__(self):
        async def get_result():
            return self._result

        return get_result().__await__()


class FakeFunctionAgent:
    """A stand-in for FunctionAgent that replays a scripted event sequence, real classes included."""

    def __init__(self, events, result=""):
        self.events = events
        self.result = result
        self.run_calls = []
        self.tools = []  # filled in by patch_agent once "FunctionAgent(tools=...)" is called

    def run(self, user_msg=None, chat_history=None, **kwargs):
        self.run_calls.append({"user_msg": user_msg, "chat_history": list(chat_history or [])})
        return FakeAgentHandler(self.tools, self.events, self.result)


def patch_agent(fake_agent):
    def construct(tools, llm, system_prompt):
        fake_agent.tools = tools
        return fake_agent

    return patch("src.rag.synthesis.agent_chat.FunctionAgent", side_effect=construct)


async def collect_events(retriever=None, **overrides):
    kwargs = {
        "message": "hello",
        "retriever": retriever or SimpleNamespace(retrieve=lambda query: []),
        "llm": Mock(),
        "user_id": "alice",
        "session_id": None,
        "allowed_document_ids": None,
    }
    kwargs.update(overrides)
    return [event async for event in handle_agent_chat(**kwargs)]


def parse(events):
    return [json.loads(event.removeprefix("data: ")) for event in events if event.strip() != "data: [DONE]"]


class AgentChatPlumbingTests(IsolatedDatabaseTestCase):
    def test_events_follow_the_established_session_token_sources_done_contract(self):
        fake_agent = FakeFunctionAgent([stream("Hel"), stream("lo", "Hello")], result="Hello")
        with patch_agent(fake_agent):
            events = asyncio.run(collect_events())

        self.assertTrue(events[0].startswith('data: {"type": "session"'))
        self.assertEqual(events[-1], "data: [DONE]\n\n")
        payloads = parse(events)
        self.assertEqual(payloads[-1]["type"], "sources")
        self.assertEqual(payloads[-1]["sources"], [])

    def test_token_deltas_are_streamed_and_the_full_answer_is_saved(self):
        fake_agent = FakeFunctionAgent([stream("Hel"), stream("lo", "Hello")], result="Hello")
        with patch_agent(fake_agent):
            events = asyncio.run(collect_events())

        payloads = parse(events)
        tokens = [p["content"] for p in payloads if p["type"] == "token"]
        self.assertEqual(tokens, ["Hel", "lo"])
        session_id = payloads[0]["session_id"]
        history = session_registry.get_session_history("alice", session_id)
        self.assertEqual([m["content"] for m in history], ["hello", "Hello"])

    def test_tool_activity_is_streamed_but_not_persisted_to_history(self):
        fake_agent = FakeFunctionAgent(
            [tool_call(query="photosynthesis"), tool_call_result(output="p.1: ..."), stream("answer")],
            result="answer",
        )
        with patch_agent(fake_agent):
            events = asyncio.run(collect_events())

        payloads = parse(events)
        self.assertEqual(
            [(p["type"], p.get("name")) for p in payloads if p["type"] in ("tool_call", "tool_result")],
            [("tool_call", "search_documents"), ("tool_result", "search_documents")],
        )
        tool_call_payload = next(p for p in payloads if p["type"] == "tool_call")
        self.assertEqual(tool_call_payload["arguments"], {"query": "photosynthesis"})
        session_id = next(p["session_id"] for p in payloads if p["type"] == "session")
        history = session_registry.get_session_history("alice", session_id)
        self.assertEqual([m["role"] for m in history], ["user", "assistant"])

    def test_a_reply_with_no_streamed_deltas_falls_back_to_the_final_result(self):
        fake_agent = FakeFunctionAgent([], result="non-streamed answer")
        with patch_agent(fake_agent):
            events = asyncio.run(collect_events())

        session_id = parse(events)[0]["session_id"]
        history = session_registry.get_session_history("alice", session_id)
        self.assertEqual(history[-1]["content"], "non-streamed answer")

    def test_an_existing_session_is_reused_and_its_prior_history_is_passed_to_the_agent(self):
        session_id, memory = session_registry.create_session("alice")
        memory.put(ChatMessage(role=MessageRole.USER, content="earlier question"))
        memory.put(ChatMessage(role=MessageRole.ASSISTANT, content="earlier answer"))
        session_registry.save_session("alice", session_id, memory)
        fake_agent = FakeFunctionAgent([stream("ok")], result="ok")

        with patch_agent(fake_agent):
            events = asyncio.run(collect_events(session_id=session_id))

        self.assertEqual(parse(events)[0]["session_id"], session_id)
        passed_history = fake_agent.run_calls[0]["chat_history"]
        self.assertEqual([m.content for m in passed_history], ["earlier question", "earlier answer"])

    def test_sources_collected_by_the_tools_reach_the_final_event(self):
        node = SimpleNamespace(
            node=SimpleNamespace(
                metadata={"file_name": "notes.pdf", "page_label": "3", "file_id": "doc-1"},
                get_content=lambda: "photosynthesis converts light into chemical energy",
            ),
            score=0.9,
        )
        retriever = SimpleNamespace(retrieve=lambda query: [node])
        fake_agent = FakeFunctionAgent([tool_call(), tool_call_result(), stream("answer")], result="answer")

        with patch_agent(fake_agent):
            events = asyncio.run(collect_events(retriever=retriever))

        sources = parse(events)[-1]["sources"]
        self.assertEqual(sources, [{"file": "notes.pdf", "page": "3", "score": 0.9}])

    def test_node_postprocessors_reach_build_document_tools(self):
        marker = object()
        fake_agent = FakeFunctionAgent([stream("ok")], result="ok")

        with patch_agent(fake_agent), patch(
            "src.rag.synthesis.agent_chat.build_document_tools", return_value=([], [])
        ) as build_tools:
            asyncio.run(collect_events(node_postprocessors=[marker]))

        build_tools.assert_called_once()
        self.assertEqual(build_tools.call_args.args[3], [marker])

    def test_a_connected_github_token_adds_github_tools_to_the_agent(self):
        github_credentials.save_token("alice", "ghp_alice_token")
        github_tool = Mock(name="github_tool")
        fake_agent = FakeFunctionAgent([stream("ok")], result="ok")

        with patch_agent(fake_agent), patch(
            "src.rag.synthesis.agent_chat.build_github_tools",
            new_callable=AsyncMock,
            return_value=[github_tool],
        ) as build_github:
            asyncio.run(collect_events())

        build_github.assert_called_once_with("ghp_alice_token")
        self.assertIn(github_tool, fake_agent.tools)

    def test_no_connected_github_token_means_no_github_tools(self):
        # No token saved for "alice" in this temp database, so build_github_tools runs for real
        # (its own no-token fast path is covered in tests/test_github_tools.py) and the agent's
        # tool list is exactly what build_document_tools contributes: search_documents + list_documents.
        fake_agent = FakeFunctionAgent([stream("ok")], result="ok")

        with patch_agent(fake_agent):
            asyncio.run(collect_events())

        self.assertEqual(len(fake_agent.tools), 2)

    def test_a_document_id_scope_reaches_the_agents_tools(self):
        node = SimpleNamespace(
            node=SimpleNamespace(metadata={"file_name": "a.pdf", "file_id": "keep"}, get_content=lambda: "kept"),
            score=1.0,
        )
        other = SimpleNamespace(
            node=SimpleNamespace(metadata={"file_name": "b.pdf", "file_id": "drop"}, get_content=lambda: "dropped"),
            score=1.0,
        )
        retriever = SimpleNamespace(retrieve=lambda query: [node, other])
        fake_agent = FakeFunctionAgent([tool_call(), tool_call_result(), stream("answer")], result="answer")

        with patch_agent(fake_agent):
            events = asyncio.run(
                collect_events(retriever=retriever, allowed_document_ids=frozenset({"keep"}))
            )

        sources = parse(events)[-1]["sources"]
        self.assertEqual([source["file"] for source in sources], ["a.pdf"])


class ChatDocumentScopeApiTests(IsolatedDatabaseTestCase):
    """The document_id ownership check at the full request level, agent mode."""

    def setUp(self):
        super().setUp()
        self.app = FastAPI()
        self.app.include_router(chat_router, dependencies=[Depends(get_current_user)])
        self.auth = AuthService("k" * 32)
        self.app.state.auth_service = self.auth
        retriever_factory = Mock()
        retriever_factory.for_user.return_value = SimpleNamespace(retrieve=lambda query: [])
        self.app.state.rag_service = RagService(retriever_factory, Mock(), [], chat_mode="agent")
        self.client = TestClient(self.app)
        self.alice_id, self.alice = self._signup("alice")
        self.bob_id, self.bob = self._signup("bob")

    def _signup(self, name):
        tokens = self.auth.signup(name, f"{name}@example.org", "password-123", "College", "2026")
        return tokens["user"]["user_id"], {"Authorization": f"Bearer {tokens['access_token']}"}

    def test_chatting_about_someone_elses_document_is_404_and_never_starts_the_agent(self):
        from src.rag.registry import documents as document_registry

        document_registry.create_document("bob-doc", self.bob_id, "b.pdf", "stored", "hash", 10)
        document_registry.mark_ready("bob-doc", 3)

        with patch("src.rag.synthesis.agent_chat.FunctionAgent") as agent_cls:
            response = self.client.post(
                "/chat", json={"question": "hi", "document_id": "bob-doc"}, headers=self.alice
            )

        self.assertEqual(response.status_code, 404)
        agent_cls.assert_not_called()

    def test_chatting_about_an_unknown_document_id_is_404(self):
        response = self.client.post(
            "/chat", json={"question": "hi", "document_id": "no-such-document"}, headers=self.alice
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
