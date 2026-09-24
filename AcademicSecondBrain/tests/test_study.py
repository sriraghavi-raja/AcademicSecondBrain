import asyncio
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import get_current_user
from src.api.study import router
from src.rag.registry import documents as document_registry
from src.services.study_service import _parse_quiz_item, generate_quiz, get_weak_topics, record_attempt
from src.services.skill_service import get_skill_graph
from tests.support import IsolatedDatabaseTestCase


class FakeLLM:
    def __init__(self, output):
        self.outputs = iter(output if isinstance(output, list) else [output])

    async def acomplete(self, prompt):
        return SimpleNamespace(text=next(self.outputs))


class StudyTests(IsolatedDatabaseTestCase):
    def setUp(self):
        super().setUp()
        document_registry.create_document("paper-id", "student-1", "paper.pdf", "stored", "hash-paper", 10)
        document_registry.mark_ready("paper-id", 3)

    def test_quiz_fixture_generation_and_validation(self):
        item = '{"question":"What is Python?","options":["Language","Database","OS","Protocol"],"correct_option":0,"explanation":"Python is a language.","concept_tag":"python"}'
        node = SimpleNamespace(
            metadata={"owner_id": "student-1", "file_id": "paper-id"},
            child_nodes=[],
            get_content=lambda: "Python is a programming language.",
        )
        index = SimpleNamespace(docstore=SimpleNamespace(docs={"node": node}))
        questions, errors = asyncio.run(generate_quiz(index, FakeLLM(item), "student-1", "paper-id", 1))
        self.assertEqual(questions[0]["correct_option"], 0)
        self.assertEqual(questions[0]["concept_tag"], "python")
        self.assertEqual(errors, [])

    def test_quiz_generation_keeps_valid_nodes_when_one_node_is_invalid(self):
        valid = '{"question":"Q","options":["A","B","C","D"],"correct_option":0,"explanation":"E","concept_tag":"python"}'
        invalid = '{"question":"Q","options":["same","same","C","D"],"correct_option":0,"explanation":"E","concept_tag":"python"}'
        owned = {"owner_id": "student-1", "file_id": "paper-id"}
        nodes = [
            SimpleNamespace(node_id="good", metadata=owned, child_nodes=[], get_content=lambda: "good"),
            SimpleNamespace(node_id="bad", metadata=owned, child_nodes=[], get_content=lambda: "bad"),
            SimpleNamespace(node_id="good-2", metadata=owned, child_nodes=[], get_content=lambda: "good-2"),
        ]
        index = SimpleNamespace(docstore=SimpleNamespace(docs={str(i): node for i, node in enumerate(nodes)}))
        questions, errors = asyncio.run(generate_quiz(index, FakeLLM([valid, invalid, valid]), "student-1", "paper-id", 3))
        self.assertEqual(len(questions), 2)
        self.assertEqual(errors, [{"node_id": "bad", "error": "Quiz options must be unique"}])

    def test_quiz_only_uses_the_callers_own_document(self):
        node = SimpleNamespace(
            node_id="n", metadata={"owner_id": "student-2", "file_id": "their-paper"}, child_nodes=[],
            get_content=lambda: "secret",
        )
        index = SimpleNamespace(docstore=SimpleNamespace(docs={"n": node}))
        llm = FakeLLM("{}")

        with self.assertRaisesRegex(ValueError, "No leaf nodes found"):
            asyncio.run(generate_quiz(index, llm, "student-1", "their-paper", 1))
        with self.assertRaisesRegex(ValueError, "No leaf nodes found"):
            asyncio.run(generate_quiz(index, llm, "student-1", "paper.pdf", 1))

    def test_malformed_quiz_items_are_rejected(self):
        invalid = '{"question":"Q","options":["same","same","three","four"],"correct_option":4,"explanation":"x","concept_tag":"python"}'
        with self.assertRaises(ValueError):
            _parse_quiz_item(invalid)

    def test_attempt_accuracy_and_weak_topic(self):
        record_attempt("student-1", "paper-id", "python", False)
        record_attempt("student-1", "paper-id", "python", True)
        record_attempt("student-1", "paper-id", "python", False)
        result = get_weak_topics("student-1", threshold=0.7)
        self.assertEqual(result[0]["concept_tag"], "Python")
        self.assertEqual(result[0]["accuracy"], 1 / 3)

    def test_generated_specific_tag_is_stored_as_fallback_topic(self):
        result = record_attempt("student-1", "paper-id", "Machine Learning Challenges", False)
        self.assertEqual(result["concept_tag"], "Machine Learning Challenges")
        self.assertEqual(get_weak_topics("student-1")[0]["concept_tag"], "Machine Learning Challenges")

    def test_quiz_attempt_appears_in_skill_graph(self):
        record_attempt("student-1", "paper-id", "Algorithms", False)
        graph = get_skill_graph("student-1")

        self.assertEqual(graph["skills"][0]["skill_name"], "Algorithms")
        self.assertEqual(graph["skills"][0]["confidence"], 0.0)
        self.assertEqual(graph["skills"][0]["evidence"][0]["source_type"], "quiz")
        self.assertEqual(graph["skills"][0]["skill_type"], "study_topic")

    def test_blank_concept_is_reported_as_batch_error(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "student-1"}
        with TestClient(app) as client:
            response = client.post(
                "/api/study/quiz/submit",
                json={"attempts": [{
                    "document_id": "paper-id",
                    "concept_tag": " ",
                    "correct": False,
                }]},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 0)
        self.assertEqual(len(response.json()["errors"]), 1)

    def test_batch_submit_isolates_invalid_items(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "student-1"}
        with TestClient(app) as client:
            response = client.post(
                "/api/study/quiz/submit",
                json={"attempts": [
                    {
                        "document_id": "paper-id",
                        "concept_tag": "python",
                        "correct": True,
                    },
                    {
                        "document_id": "paper-id",
                        "concept_tag": " ",
                        "correct": False,
                    },
                ]},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(len(response.json()["errors"]), 1)


if __name__ == "__main__":
    unittest.main()