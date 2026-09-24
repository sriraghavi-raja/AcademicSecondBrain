"""Admin-facing endpoints for aggregating students by skill: GET /api/admin/skills (the filter's
skill list) and GET /api/admin/students/by-skill (the actual match).
"""

import unittest
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.admin import router as admin_router
from src.api.auth import get_auth_service, get_current_user
from src.services.auth_service import AuthService
from src.rag.registry import skills as skill_registry
from tests.support import IsolatedDatabaseTestCase


class StudentSearchApiTests(IsolatedDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.auth = AuthService("k" * 32)
        self.app = FastAPI()
        self.app.include_router(admin_router)
        self.app.dependency_overrides[get_auth_service] = lambda: self.auth
        self.app.dependency_overrides[get_current_user] = lambda: {
            "user_id": "admin-id", "role": "admin"
        }
        self.client = TestClient(self.app)
        self.alice_id = self._signup("alice", "alice@example.org")
        self.bob_id = self._signup("bob", "bob@example.org")

    def _signup(self, name, email):
        return self.auth.signup(name, email, "password-123", "College", "2026")["user"]["user_id"]

    def _give(self, student_id, skill_name, confidence, source_ref="ref"):
        skill_registry.upsert_skill(student_id, skill_name)
        skill_registry.upsert_skill_evidence(
            student_id, skill_name, skill_name.lower(), "manual", source_ref, confidence
        )

    def test_the_skill_list_reflects_what_students_actually_have(self):
        self._give(self.alice_id, "Python", 0.9)
        self._give(self.bob_id, "SQL", 0.8)

        response = self.client.get("/api/admin/skills")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"skills": ["Python", "SQL"]})

    def test_a_student_cannot_list_skills_or_search_students(self):
        self.app.dependency_overrides[get_current_user] = lambda: {
            "user_id": self.alice_id, "role": "student"
        }
        self.assertEqual(self.client.get("/api/admin/skills").status_code, 403)
        self.assertEqual(self.client.get("/api/admin/students/by-skill?skill=Python").status_code, 403)

    def test_searching_by_skill_returns_matching_students_with_their_confidence(self):
        self._give(self.alice_id, "Python", 0.9)
        self._give(self.bob_id, "SQL", 0.8)

        response = self.client.get("/api/admin/students/by-skill?skill=Python")

        self.assertEqual(response.status_code, 200)
        students = response.json()["students"]
        self.assertEqual(len(students), 1)
        self.assertEqual(students[0]["user_id"], self.alice_id)
        self.assertEqual(students[0]["name"], "alice")
        self.assertEqual(students[0]["matched_skills"], [{"skill_name": "Python", "confidence": 0.9}])

    def test_match_any_is_the_default(self):
        self._give(self.alice_id, "Python", 0.9)
        self._give(self.bob_id, "SQL", 0.8)

        response = self.client.get("/api/admin/students/by-skill?skill=Python&skill=SQL")

        ids = {student["user_id"] for student in response.json()["students"]}
        self.assertEqual(ids, {self.alice_id, self.bob_id})

    def test_match_all_requires_every_requested_skill(self):
        self._give(self.alice_id, "Python", 0.9)
        self._give(self.alice_id, "SQL", 0.9)
        self._give(self.bob_id, "Python", 0.9)

        response = self.client.get("/api/admin/students/by-skill?skill=Python&skill=SQL&match=all")

        ids = {student["user_id"] for student in response.json()["students"]}
        self.assertEqual(ids, {self.alice_id})

    def test_min_confidence_filters_out_weaker_evidence(self):
        self._give(self.alice_id, "Python", 0.9)
        self._give(self.bob_id, "Python", 0.3)

        response = self.client.get("/api/admin/students/by-skill?skill=Python&min_confidence=0.7")

        ids = {student["user_id"] for student in response.json()["students"]}
        self.assertEqual(ids, {self.alice_id})

    def test_no_skill_given_returns_no_students_not_everyone(self):
        self._give(self.alice_id, "Python", 0.9)

        response = self.client.get("/api/admin/students/by-skill")

        self.assertEqual(response.json(), {"students": []})

    def test_an_out_of_range_confidence_is_rejected(self):
        response = self.client.get("/api/admin/students/by-skill?skill=Python&min_confidence=1.5")

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
