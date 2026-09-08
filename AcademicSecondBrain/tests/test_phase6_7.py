import asyncio
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.services.interview_service import continue_interview, end_interview, start_interview
from src.services.study_service import build_study_plan, export_study_plan, parse_syllabus
from src.rag.registry import database, study as study_registry


class FakeLLM:
    def __init__(self, outputs):
        self.outputs = iter(outputs if isinstance(outputs, list) else [outputs])

    async def acomplete(self, prompt):
        return SimpleNamespace(text=next(self.outputs))


class Phase67Tests(unittest.TestCase):
    def setUp(self):
        self.database = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.database.close()
        self.old_path = database.DB_PATH
        database.DB_PATH = self.database.name
        study_registry.init_db()

    def tearDown(self):
        database.DB_PATH = self.old_path
        os.unlink(self.database.name)

    def test_parse_syllabus_fixture_formats(self):
        nodes = [SimpleNamespace(metadata={"file_name": "syllabus.pdf"}, child_nodes=[], get_content=lambda: "Week 1: Python\nWeek 2: SQL")]
        index = SimpleNamespace(docstore=SimpleNamespace(docs={"1": nodes[0]}))
        payload = '{"topics":[{"topic":"Python","date_or_week":"Week 1","weight":1},{"topic":"SQL","date_or_week":"Week 2","weight":1}]}'
        result = asyncio.run(parse_syllabus(index, FakeLLM(payload), "syllabus.pdf"))
        self.assertEqual(len(result["topics"]), 2)

    def test_weak_topics_receive_more_sessions_and_ics_exports(self):
        study_registry.replace_syllabus_topics("syllabus", [
            {"topic": "Python", "date_or_week": "Week 1", "weight": 1},
            {"topic": "SQL", "date_or_week": "Week 2", "weight": 1},
        ])
        plan = build_study_plan("student", "syllabus", [{"concept_tag": "Python", "accuracy": 0.2}])
        self.assertEqual(sum(session["topic"] == "Python" for session in plan["sessions"]), 2)
        self.assertEqual(sum(session["topic"] == "SQL" for session in plan["sessions"]), 1)
        ics_text = export_study_plan(plan["plan_id"])
        self.assertIn("BEGIN:VCALENDAR", ics_text)
        self.assertIn("Study: Python", ics_text)

    def test_interview_lifecycle(self):
        with patch("src.services.interview_service.get_skill_graph", return_value={"skills": []}), \
             patch("src.services.interview_service.get_weak_topics", return_value=[]):
            start = asyncio.run(start_interview("student", "Python Developer", "technical", FakeLLM("What is Python?")))
        continued = asyncio.run(continue_interview(start["session_id"], "A programming language.", FakeLLM("Explain its typing.")))
        ended = end_interview(continued["session_id"])
        self.assertEqual(start["session_id"], continued["session_id"])
        self.assertEqual(len(ended["messages"]), 3)


if __name__ == "__main__":
    unittest.main()