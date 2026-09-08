import json
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import get_current_user
from src.api.skills import router
from src.rag.registry import skills as skill_registry
from src.rag.registry import database
from src.services.skill_service import add_evidence, get_skill_graph, merge_taxonomy_match


class SkillStoreTests(unittest.TestCase):
    def setUp(self):
        self.database = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.database.close()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.database.name
        skill_registry.init_db()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        os.unlink(self.database.name)

    def _connection(self):
        import sqlite3
        return sqlite3.connect(self.database.name)

    def test_taxonomy_fixture(self):
        self.assertEqual(merge_taxonomy_match(" PY "), "Python")
        self.assertEqual(merge_taxonomy_match("machine learning"), "Machine Learning")
        self.assertIsNone(merge_taxonomy_match("unknown-term"))

    def test_evidence_round_trip_and_graph_merge(self):
        add_evidence("student-1", "python", "manual", "a", 0.8)
        add_evidence("student-1", "py", "quiz", "b", 0.95)
        add_evidence("student-1", "python", "manual", "a", 0.9)
        graph = get_skill_graph("student-1")

        self.assertEqual(len(graph["skills"]), 1)
        self.assertEqual(graph["skills"][0]["skill_name"], "Python")
        self.assertEqual(graph["skills"][0]["confidence"], 0.95)
        self.assertEqual(len(graph["skills"][0]["evidence"]), 2)

        connection = self._connection()
        rows = connection.execute("select * from skill_evidence").fetchall()
        connection.close()
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            next(row[6] for row in rows if row[4] == "manual" and row[5] == "a"),
            0.9,
        )

    def test_resync_updates_existing_evidence(self):
        first = add_evidence("student-1", "python", "github", "repo-a", 0.5)
        second = add_evidence("student-1", "python", "github", "repo-a", 0.95)
        graph = get_skill_graph("student-1")

        self.assertEqual(first["evidence_id"], second["evidence_id"])
        self.assertEqual(graph["skills"][0]["confidence"], 0.95)
        self.assertEqual(len(graph["skills"][0]["evidence"]), 1)

    def test_unknown_term_returns_http_400(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "student-1"}
        with TestClient(app) as client:
            response = client.post(
            "/api/skills/evidence",
                json={
                    "raw_term": "not-a-real-skill",
                    "source_type": "manual",
                    "source_ref": "test",
                    "confidence": 0.8,
                },
            )
        self.assertEqual(response.status_code, 400)

    def test_achievements_crud_round_trip(self):
        achievement_id = skill_registry.insert_achievement(
            "student-1", "Python badge", "Completed", "2026-09-05", json.dumps({"level": 1})
        )
        achievements = skill_registry.select_achievements("student-1")

        self.assertEqual(achievement_id, achievements[0]["achievement_id"])
        self.assertEqual(achievements[0]["name"], "Python badge")

    def test_routes_post_and_get(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "student-1"}
        with patch("src.api.skills.add_evidence", return_value={"skill_name": "Python"}) as add:
            with TestClient(app) as client:
                response = client.post(
                    "/api/skills/evidence",
                    json={
                        "raw_term": "python",
                        "source_type": "manual",
                        "source_ref": "test",
                        "confidence": 0.8,
                    },
                )
        self.assertEqual(response.status_code, 200)
        add.assert_called_once()


if __name__ == "__main__":
    unittest.main()