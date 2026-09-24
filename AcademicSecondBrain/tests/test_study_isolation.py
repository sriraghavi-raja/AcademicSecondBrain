import asyncio
import json
import unittest
from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api import study_router
from src.api.auth import get_current_user
from src.rag.registry import database
from src.rag.registry import documents as document_registry
from src.rag.registry import study as study_registry
from src.services.auth_service import AuthService
from src.services.study_service import build_study_plan, export_study_plan, generate_quiz, parse_syllabus, record_attempt
from tests.support import ORCHID, IndexedTestCase, IsolatedDatabaseTestCase, article

QUIZ_ITEM = json.dumps({
    "question": "Q", "options": ["A", "B", "C", "D"], "correct_option": 0,
    "explanation": "E", "concept_tag": "python",
})
SYLLABUS = json.dumps({"topics": [
    {"topic": "Python", "date_or_week": "Week 1", "weight": 1},
    {"topic": "SQL", "date_or_week": "Week 2", "weight": 1},
]})


class FakeLLM:
    async def acomplete(self, prompt):
        return SimpleNamespace(text=SYLLABUS if "Extract syllabus topics" in prompt else QUIZ_ITEM)


def add_document(owner, file_id, ready=True):
    document_registry.create_document(file_id, owner, "paper.pdf", "stored", f"hash-{file_id}", 10)
    if ready:
        document_registry.mark_ready(file_id, 3)


def index_node(owner, file_id):
    return SimpleNamespace(
        node_id=f"{file_id}-node",
        metadata={"owner_id": owner, "file_id": file_id},
        child_nodes=[],
        get_content=lambda: "Week 1: Python. Week 2: SQL.",
    )


def topics(*names):
    return [{"topic": name, "date_or_week": None, "weight": None} for name in names]


class StudyRegistryIsolationTests(IsolatedDatabaseTestCase):
    def test_syllabus_topics_are_stored_per_student(self):
        study_registry.replace_syllabus_topics("alice", "syllabus", topics("Python"))
        study_registry.replace_syllabus_topics("bob", "syllabus", topics("Rust", "Go"))

        self.assertEqual([t["topic"] for t in study_registry.select_syllabus_topics("alice", "syllabus")], ["Python"])
        self.assertEqual([t["topic"] for t in study_registry.select_syllabus_topics("bob", "syllabus")], ["Rust", "Go"])
        self.assertEqual(study_registry.select_syllabus_topics("carol", "syllabus"), [])

    def test_legacy_syllabus_table_is_migrated_and_legacy_rows_are_dropped(self):
        with database.get_db_connection() as connection:
            connection.execute("DROP TABLE syllabus_topics")
            connection.execute(
                "CREATE TABLE syllabus_topics (topic_id INTEGER PRIMARY KEY AUTOINCREMENT, syllabus_id TEXT NOT NULL, "
                "topic TEXT NOT NULL, date_or_week TEXT, weight REAL, UNIQUE(syllabus_id, topic, date_or_week))"
            )
            connection.execute("INSERT INTO syllabus_topics (syllabus_id, topic) VALUES ('paper.pdf', 'Python')")
            connection.commit()

        study_registry.init_db()
        study_registry.init_db()

        with database.get_db_connection() as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(syllabus_topics)")}
            legacy_rows = connection.execute("SELECT COUNT(*) FROM syllabus_topics").fetchone()[0]
        self.assertIn("student_id", columns)
        self.assertEqual(legacy_rows, 0)
        study_registry.replace_syllabus_topics("alice", "syllabus", topics("Python"))
        study_registry.replace_syllabus_topics("bob", "syllabus", topics("Python"))

    def test_a_student_cannot_build_a_plan_from_someone_elses_syllabus(self):
        study_registry.replace_syllabus_topics("alice", "syllabus", topics("Python"))

        with self.assertRaisesRegex(ValueError, "No parsed syllabus"):
            build_study_plan("bob", "syllabus")
        self.assertEqual(len(build_study_plan("alice", "syllabus")["sessions"]), 1)

    def test_study_plans_can_only_be_exported_by_their_owner(self):
        study_registry.replace_syllabus_topics("alice", "syllabus", topics("Python"))
        plan_id = build_study_plan("alice", "syllabus")["plan_id"]

        self.assertIn("BEGIN:VCALENDAR", export_study_plan("alice", plan_id))
        with self.assertRaisesRegex(ValueError, "Study plan not found"):
            export_study_plan("bob", plan_id)
        with self.assertRaisesRegex(ValueError, "Study plan not found"):
            export_study_plan("alice", "no-such-plan")

    def test_attempts_need_a_ready_document_the_student_owns(self):
        add_document("alice", "alice-doc")
        add_document("alice", "still-processing", ready=False)
        add_document("bob", "bob-doc")

        self.assertEqual(record_attempt("alice", "alice-doc", "python", True)["document_id"], "alice-doc")
        for document_id in ("bob-doc", "still-processing", "no-such-document"):
            with self.assertRaisesRegex(ValueError, "Document not found"):
                record_attempt("alice", document_id, "python", True)
        self.assertEqual(len(study_registry.select_quiz_attempts("alice")), 1)


class StudyApiIsolationTests(IsolatedDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.app = FastAPI()
        self.app.include_router(study_router, dependencies=[Depends(get_current_user)])
        self.auth = AuthService("k" * 32)
        self.app.state.auth_service = self.auth
        self.app.state.llm = FakeLLM()
        self.client = TestClient(self.app)
        self.alice_id, self.alice = self._signup("alice")
        self.bob_id, self.bob = self._signup("bob")
        add_document(self.alice_id, "alice-doc")
        add_document(self.bob_id, "bob-doc")
        self.app.state.index = SimpleNamespace(docstore=SimpleNamespace(docs={
            "a": index_node(self.alice_id, "alice-doc"),
            "b": index_node(self.bob_id, "bob-doc"),
        }))

    def _signup(self, name):
        tokens = self.auth.signup(name, f"{name}@example.org", "password-123", "College", "2026")
        return tokens["user"]["user_id"], {"Authorization": f"Bearer {tokens['access_token']}"}

    def quiz(self, headers, document_id):
        return self.client.post("/api/study/quiz", json={"document_id": document_id, "num_questions": 1}, headers=headers)

    def plan(self, headers, syllabus_id, **extra):
        return self.client.post("/api/study/plan", json={"syllabus_id": syllabus_id, **extra}, headers=headers)

    def test_quiz_for_another_users_or_an_unknown_document_is_404(self):
        self.assertEqual(self.quiz(self.alice, "bob-doc").status_code, 404)
        self.assertEqual(self.quiz(self.alice, "no-such-document").status_code, 404)

        own = self.quiz(self.alice, "alice-doc")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.json()["generated_count"], 1)

    def test_study_plan_for_another_users_document_is_404(self):
        self.assertEqual(self.plan(self.alice, "bob-doc").status_code, 404)

        own = self.plan(self.alice, "alice-doc")
        self.assertEqual(own.status_code, 200)
        self.assertEqual({s["topic"] for s in own.json()["sessions"]}, {"Python", "SQL"})

    def test_plan_export_is_private_to_the_owner(self):
        plan_id = self.plan(self.alice, "alice-doc").json()["plan_id"]

        self.assertEqual(self.client.get(f"/api/study/plan/{plan_id}/export", headers=self.bob).status_code, 404)
        self.assertEqual(self.client.get("/api/study/plan/no-such-plan/export", headers=self.alice).status_code, 404)
        exported = self.client.get(f"/api/study/plan/{plan_id}/export", headers=self.alice)
        self.assertEqual(exported.status_code, 200)
        self.assertIn("BEGIN:VCALENDAR", exported.text)
        self.assertEqual(self.client.get(f"/api/study/plan/{plan_id}/export").status_code, 401)

    def test_quiz_submission_reports_a_foreign_document_as_a_batch_error(self):
        response = self.client.post(
            "/api/study/quiz/submit",
            json={"attempts": [
                {"document_id": "alice-doc", "concept_tag": "python", "correct": True},
                {"document_id": "bob-doc", "concept_tag": "python", "correct": True},
            ]},
            headers=self.alice,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(len(body["errors"]), 1)
        self.assertIn("Document not found", body["errors"][0]["error"])

    def test_malformed_weak_topics_are_a_422_not_a_500(self):
        malformed = self.plan(self.alice, "alice-doc", weak_topics=[{"topic": "Python"}])
        self.assertEqual(malformed.status_code, 422)

        weak = [{"concept_tag": "Python", "accuracy": 0.2, "attempt_count": 3, "last_answered_at": "2026-09-19"}]
        accepted = self.plan(self.alice, "alice-doc", weak_topics=weak)
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(sum(s["topic"] == "Python" for s in accepted.json()["sessions"]), 2)
        self.assertEqual(sum(s["topic"] == "SQL" for s in accepted.json()["sessions"]), 1)


class StudyOverRealUploadsTests(IndexedTestCase):
    """Uses documents that really went through the upload pipeline, so the metadata the study code
    looks for is the metadata uploads actually stamp."""

    def test_quiz_and_syllabus_work_for_the_owner_of_an_uploaded_document_only(self):
        document_id = self.upload("alice", "syllabus.txt", article(ORCHID))["document_id"]
        llm = FakeLLM()

        questions, errors = asyncio.run(generate_quiz(self.index, llm, "alice", document_id, 2))
        parsed = asyncio.run(parse_syllabus(self.index, llm, "alice", document_id))

        self.assertEqual((len(questions), errors), (2, []))
        self.assertEqual([t["topic"] for t in parsed["topics"]], ["Python", "SQL"])
        self.assertEqual([t["topic"] for t in study_registry.select_syllabus_topics("alice", document_id)], ["Python", "SQL"])
        with self.assertRaisesRegex(ValueError, "No leaf nodes found"):
            asyncio.run(generate_quiz(self.index, llm, "bob", document_id, 2))
        with self.assertRaisesRegex(ValueError, "No syllabus content"):
            asyncio.run(parse_syllabus(self.index, llm, "bob", document_id))
        self.assertEqual(study_registry.select_syllabus_topics("bob", document_id), [])


if __name__ == "__main__":
    unittest.main()
