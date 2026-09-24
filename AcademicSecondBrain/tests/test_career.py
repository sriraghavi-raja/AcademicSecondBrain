import asyncio
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.services.career_service import (
    extract_certification,
    generate_project_bullets,
    generate_resume,
    group_skills_by_category,
    suggest_skill_gaps,
)
from tests.support import IsolatedDatabaseTestCase


class FakeLLM:
    def __init__(self, output):
        self.output = output
        self.prompts = []

    async def acomplete(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(text=self.output)


class CareerTests(IsolatedDatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.profile = {
            "student_id": "student-1", "full_name": "Sri Raghavi N", "email": "student@example.com",
            "phone": "123", "location": "Coimbatore", "college_name": "Example Institute",
            "degree": "B.Tech", "branch": "AI and Data Science", "college_start": "2023",
            "college_end": "2027", "cgpa": "9.0", "school_name": "Example School",
            "school_detail": "Higher Secondary", "school_dates": "2021-2023", "school_score": "95%",
        }

    def test_group_skills_excludes_study_topics_and_quiz_only_skills(self):
        graph = {"skills": [
            {"skill_name": "Python", "skill_type": "taxonomy", "evidence": [{"source_type": "manual"}]},
            {"skill_name": "Algorithms", "skill_type": "study_topic", "evidence": [{"source_type": "quiz"}]},
            {"skill_name": "Machine Learning", "skill_type": "taxonomy", "evidence": [{"source_type": "quiz"}]},
        ]}
        self.assertEqual(group_skills_by_category(graph), {"Programming Languages": ["Python"]})

    def test_project_bullets_reject_unsupported_numbers(self):
        project = {"title": "Project", "tech_stack": "Python", "description_text": "Built a Python API."}
        with self.assertRaisesRegex(ValueError, "unsupported number"):
            asyncio.run(generate_project_bullets(project, FakeLLM('{"bullets":[{"text":"Improved accuracy by 95%."}]}')))

    def test_empty_project_description_has_no_bullets(self):
        project = {"title": "Private Project", "tech_stack": "Python", "description_text": ""}
        self.assertEqual(asyncio.run(generate_project_bullets(project, FakeLLM("{}"))), [])

    def test_structured_resume_renders_once_and_uses_target_role(self):
        project = {
            "project_id": 1, "title": "Academic RAG Assistant", "tech_stack": "Python, FastAPI",
            "source_type": "manual", "source_ref": "manual:project",
            "description_text": "Built a Python API with FastAPI.",
        }
        graph = {"skills": [{"skill_name": "Python", "skill_type": "taxonomy", "evidence": [{"source_type": "manual"}]}]}
        llm = FakeLLM('{"bullets":[{"text":"Built a Python API with FastAPI."},{"text":"Built a Python API with FastAPI."}]}')
        with patch("src.services.career_service.get_profile", return_value=self.profile), \
             patch("src.services.career_service.get_skill_graph", return_value=graph), \
             patch("src.services.career_service.get_projects", return_value=[project]), \
             patch("src.services.career_service.get_achievements", return_value=[]):
            with tempfile.TemporaryDirectory() as output_dir:
                result = asyncio.run(generate_resume("student-1", llm, "Python Developer", output_dir))
                self.assertTrue(os.path.exists(result["file_path"]))
                self.assertEqual(len(result["data"]["projects"][0]["bullets"]), 1)
                self.assertIn("Python Developer", llm.prompts[0])

    def test_certificate_uses_filename_when_model_omits_title(self):
        llm = FakeLLM('{"issuer":"Coursera","date":"2026-09-05","skills_mentioned":["SQL"]}')
        with patch("src.services.career_service.load_documents_from_path", return_value=[SimpleNamespace(text="Advanced SQL certificate")]), \
             patch("src.rag.registry.skills.insert_achievement", return_value=7), \
             patch("src.services.career_service.add_evidence") as add_evidence:
            result = asyncio.run(
                extract_certification("certificate.pdf", llm, "student-1", "sql_advanced certificate (1).pdf")
            )
        self.assertEqual(result["title"], "sql advanced certificate (1)")
        add_evidence.assert_called_once_with("student-1", "SQL", "certification", "sql advanced certificate (1)", 0.75)

    def test_skill_gap_analysis_parses_structured_model_response(self):
        llm = FakeLLM('{"skills":["Python","SQL","Docker"]}')
        graph = {"skills": [{"skill_name": "Python", "skill_type": "taxonomy"}]}
        with patch("src.services.career_service.get_skill_graph", return_value=graph), \
             patch("src.services.career_service.record_career_run") as record_run:
            result = asyncio.run(
                suggest_skill_gaps("student-1", "Requires Python, SQL, and Docker.", llm)
            )
        self.assertEqual(result["required_skills"], ["Python", "SQL", "Docker"])
        self.assertEqual(
            [gap["skill_name"] for gap in result["gaps"]],
            ["SQL", "Docker"],
        )
        self.assertIn("Return JSON only", llm.prompts[0])
        record_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
