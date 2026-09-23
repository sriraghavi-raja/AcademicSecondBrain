import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import admin_router, auth_router
from src.rag.ingestion import ingester
from src.rag.registry import auth as auth_registry
from src.rag.registry import career, database
from src.rag.registry import documents as document_registry
from src.rag.registry import github_credentials
from src.rag.registry import sessions as session_registry
from src.rag.registry import skills, study, user_data
from src.services.account_service import AccountService
from src.services.auth_service import AuthError, AuthService
from tests.support import GRANITE, ORCHID, QUARTZ, IndexedTestCase, article


class AccountTestCase(IndexedTestCase):
    def setUp(self):
        super().setUp()
        self.auth = AuthService("k" * 32)
        self.output_dir = self.workspace_root / "outputs"
        self.output_dir.mkdir()
        self.accounts = AccountService(self.auth, self.documents, output_dir=str(self.output_dir))
        self.alice_tokens = self.auth.signup("alice", "alice@example.org", "password-123", "College", "2026")
        self.bob_tokens = self.auth.signup("bob", "bob@example.org", "password-123", "College", "2026")
        self.alice = self.alice_tokens["user"]["user_id"]
        self.bob = self.bob_tokens["user"]["user_id"]

    def populate(self, user_id, first_token, second_token):
        """Gives a user one row in every table, two indexed documents, and a generated resume."""
        first = self.upload(user_id, "first.txt", article(first_token))["document_id"]
        self.upload(user_id, "second.txt", article(second_token))
        session_registry.create_session(user_id, "chat")
        session_registry.create_session(user_id, "interview")
        skills.upsert_skill(user_id, "Python")
        skills.upsert_skill_evidence(user_id, "Python", "python", "manual", "ref", 0.9)
        skills.insert_achievement(user_id, "Certificate", None, None, "{}")
        study.insert_quiz_attempt(user_id, first, "Python", True)
        study.replace_syllabus_topics(user_id, first, [{"topic": "Python", "date_or_week": None, "weight": None}])
        study.insert_study_plan(f"plan-{user_id}", user_id, first, "{}")
        career.upsert_profile(user_id, {"full_name": user_id})
        career.upsert_project(user_id, "Project", "Python", "manual", f"ref-{user_id}", "Built a thing.")
        career.record_career_run(user_id, "resume", {})
        github_credentials.save_token(user_id, f"ghp_{user_id}_token")
        (self.output_dir / f"{user_id}_resume.docx").write_bytes(b"resume")

    def rows(self, user_id):
        with database.get_db_connection() as connection:
            return {
                table: connection.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (user_id,)).fetchone()[0]
                for table, column in user_data.OWNED_TABLES
            }

    def nodes(self, user_id):
        return [n for n in self.index.docstore.docs.values() if n.metadata.get("owner_id") == user_id]

    def refresh_sessions(self, user_id):
        with auth_registry.get_db_connection() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM refresh_sessions WHERE user_id = ?", (user_id,)
            ).fetchone()[0]


class DeleteUserTests(AccountTestCase):
    def test_deleting_a_user_removes_everything_they_own(self):
        self.populate(self.alice, ORCHID, QUARTZ)
        self.assertTrue(all(count >= 1 for count in self.rows(self.alice).values()), self.rows(self.alice))

        self.accounts.delete_user(self.alice)

        self.assertEqual(self.rows(self.alice), {table: 0 for table, _ in user_data.OWNED_TABLES})
        self.assertIsNone(self.auth.get_user(self.alice))
        self.assertEqual(self.refresh_sessions(self.alice), 0)
        with self.assertRaises(AuthError):
            self.auth.refresh(self.alice_tokens["refresh_token"])
        with self.assertRaises(AuthError):
            self.auth.user_from_access_token(self.alice_tokens["access_token"])
        self.assertEqual(self.nodes(self.alice), [])
        self.assertEqual(self.index.vector_store.client.count(), 0)
        self.assertFalse(Path(self.upload_dir, self.alice).exists())
        self.assertFalse((self.output_dir / f"{self.alice}_resume.docx").exists())
        self.assertEqual(self.retrieve(self.alice, ORCHID), [])
        self.assertIsNone(self.factory.bm25_for(self.alice))

    def test_other_users_keep_all_their_data(self):
        self.populate(self.alice, ORCHID, QUARTZ)
        self.populate(self.bob, GRANITE, GRANITE + " second")
        bob_rows = self.rows(self.bob)
        bob_nodes = len(self.nodes(self.bob))

        self.accounts.delete_user(self.alice)

        self.assertEqual(self.rows(self.bob), bob_rows)
        self.assertEqual(len(self.nodes(self.bob)), bob_nodes)
        self.assertEqual(self.filenames(self.bob), ["first.txt", "second.txt"])
        self.assertTrue(self.retrieve(self.bob, GRANITE))
        self.assertGreater(self.index.vector_store.client.count(), 0)
        self.assertEqual(len([p for p in self.stored_files() if self.bob in p.parts]), 2)
        self.assertTrue((self.output_dir / f"{self.bob}_resume.docx").exists())
        self.assertEqual(self.auth.login("bob", "password-123")["user"]["user_id"], self.bob)
        self.assertGreaterEqual(self.refresh_sessions(self.bob), 1)

    def test_indexed_nodes_without_a_document_record_are_removed_too(self):
        leftover = Path(self.upload_dir, self.alice, "orphan")
        leftover.mkdir(parents=True)
        (leftover / "document.txt").write_text(article(ORCHID))
        ingester.ingest_new_documents(
            [str(leftover / "document.txt")], self.index, self.alice, "orphan", "orphan.txt", persist_dir=self.persist_dir
        )
        self.assertGreater(len(self.nodes(self.alice)), 0)
        self.assertEqual(document_registry.get_document(self.alice, "orphan"), None)

        self.accounts.delete_user(self.alice)

        self.assertEqual(self.nodes(self.alice), [])
        self.assertEqual(self.index.vector_store.client.count(), 0)
        self.assertFalse(leftover.exists())

    def test_a_failed_cleanup_keeps_the_account_so_the_admin_can_retry(self):
        self.populate(self.alice, ORCHID, QUARTZ)

        with patch("src.services.account_service.user_data.delete_user_records", side_effect=RuntimeError("disk error")):
            with self.assertRaises(RuntimeError):
                self.accounts.delete_user(self.alice)

        self.assertIsNotNone(self.auth.get_user(self.alice))
        self.assertEqual(self.nodes(self.alice), [])
        self.accounts.delete_user(self.alice)
        self.assertIsNone(self.auth.get_user(self.alice))
        self.assertEqual(self.rows(self.alice), {table: 0 for table, _ in user_data.OWNED_TABLES})

    def test_deleting_an_unknown_user_is_not_found(self):
        with self.assertRaises(AuthError):
            self.accounts.delete_user("no-such-user")


class SchemaCoverageTests(IndexedTestCase):
    def test_every_table_that_stores_user_data_is_covered_by_the_cascade(self):
        """Fails when a new table with a user column is added but forgotten in user_data.OWNED_TABLES."""
        found = {}
        with database.get_db_connection() as connection:
            tables = [
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
            ]
            for table in tables:
                columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
                user_columns = [column for column in columns if column in ("student_id", "owner_id", "user_id")]
                if user_columns:
                    found[table] = user_columns[0]

        self.assertEqual(found, dict(user_data.OWNED_TABLES))


class AdminDeleteApiTests(AccountTestCase):
    def setUp(self):
        super().setUp()
        with patch.dict("os.environ", {"ADMIN_SIGNUP_KEY": "initial-admin-key"}):
            admin_tokens = self.auth.signup(
                "boss", "boss@example.org", "password-123", "College", "2026", "admin", "initial-admin-key"
            )
        self.admin_id = admin_tokens["user"]["user_id"]
        self.admin = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
        self.student = {"Authorization": f"Bearer {self.alice_tokens['access_token']}"}
        app = FastAPI()
        app.include_router(auth_router)
        app.include_router(admin_router)
        app.state.auth_service = self.auth
        app.state.account_service = self.accounts
        self.client = TestClient(app)

    def test_admin_delete_removes_the_users_data_and_locks_them_out(self):
        self.populate(self.alice, ORCHID, QUARTZ)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.student).status_code, 200)

        response = self.client.delete(f"/api/admin/users/{self.alice}", headers=self.admin)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.rows(self.alice), {table: 0 for table, _ in user_data.OWNED_TABLES})
        self.assertEqual(self.nodes(self.alice), [])
        self.assertEqual(self.client.get("/api/auth/me", headers=self.student).status_code, 401)
        self.assertEqual(
            self.client.post("/api/auth/refresh", json={"refresh_token": self.alice_tokens["refresh_token"]}).status_code,
            401,
        )

    def test_students_cannot_delete_accounts(self):
        response = self.client.delete(f"/api/admin/users/{self.bob}", headers=self.student)

        self.assertEqual(response.status_code, 403)
        self.assertIsNotNone(self.auth.get_user(self.bob))

    def test_unknown_users_are_404_and_admins_cannot_delete_themselves(self):
        self.assertEqual(self.client.delete("/api/admin/users/no-such-user", headers=self.admin).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/admin/users/{self.admin_id}", headers=self.admin).status_code, 400)
        self.assertIsNotNone(self.auth.get_user(self.admin_id))


if __name__ == "__main__":
    unittest.main()
