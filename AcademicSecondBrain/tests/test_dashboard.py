import os
import tempfile
import unittest

from src.rag.registry import career, database, skills, study
from src.services.dashboard_service import get_dashboard


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.database_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.database_file.close()
        self.old_path = database.DB_PATH
        database.DB_PATH = self.database_file.name
        skills.init_db()
        study.init_db()
        career.init_db()

    def tearDown(self):
        database.DB_PATH = self.old_path
        os.unlink(self.database_file.name)

    def test_aggregation_contains_all_student_features(self):
        career.upsert_profile("student", {"full_name": "Student"})
        skills.upsert_skill("student", "Python", "taxonomy")
        skills.upsert_skill_evidence("student", "Python", "python", "manual", "profile", 0.9)
        skills.insert_achievement("student", "Python certificate", "Issuer", "2026-01-01", '{"source":"certification"}')
        study.insert_quiz_attempt("student", "paper.pdf", "Python", False)
        career.upsert_project("student", "Project", "Python", "manual", "manual:project", "Built a Python API.")
        career.record_career_run("student", "gap-analysis", {"gaps": [{"skill_name": "Docker"}]})

        dashboard = get_dashboard("student")

        self.assertEqual(dashboard["profile"]["full_name"], "Student")
        self.assertEqual(dashboard["summary"]["skill_count"], 1)
        self.assertEqual(dashboard["summary"]["project_count"], 1)
        self.assertEqual(dashboard["summary"]["achievement_count"], 1)
        self.assertEqual(dashboard["weak_topics"][0]["concept_tag"], "Python")
        self.assertIn("gap-analysis", dashboard["last_runs"])

    def test_empty_student_degrades_gracefully(self):
        dashboard = get_dashboard("new-student")

        self.assertIsNone(dashboard["profile"])
        self.assertEqual(dashboard["skills"], [])
        self.assertEqual(dashboard["weak_topics"], [])
        self.assertEqual(dashboard["achievements"], [])
        self.assertEqual(dashboard["projects"], [])
        self.assertEqual(dashboard["last_runs"], {})
        self.assertEqual(dashboard["summary"]["skill_count"], 0)

    def test_student_indexes_exist(self):
        import sqlite3

        connection = sqlite3.connect(self.database_file.name)
        index_names = {
            row[1]
            for table in ("skills", "skill_evidence", "achievements", "quiz_attempts", "projects", "student_profile")
            for row in connection.execute(f"PRAGMA index_list({table})")
        }
        connection.close()
        self.assertIn("idx_skills_student_id", index_names)
        self.assertIn("idx_skill_evidence_student_id", index_names)
        self.assertIn("idx_achievements_student_id", index_names)
        self.assertIn("idx_quiz_attempts_student_id", index_names)
        self.assertIn("idx_projects_student_id", index_names)
        self.assertIn("idx_student_profile_student_id", index_names)


if __name__ == "__main__":
    unittest.main()