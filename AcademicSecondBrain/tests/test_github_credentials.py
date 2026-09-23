"""A student's own GitHub token: one per user, encrypted at rest, never readable in plaintext elsewhere."""

import unittest

from src.rag.registry import database
from src.rag.registry import github_credentials as credentials
from tests.support import IsolatedDatabaseTestCase


class SaveAndGetTokenTests(IsolatedDatabaseTestCase):
    def test_a_saved_token_is_returned_decrypted(self):
        credentials.save_token("alice", "ghp_alice_token")

        self.assertEqual(credentials.get_token("alice"), "ghp_alice_token")

    def test_an_unknown_user_has_no_token(self):
        self.assertIsNone(credentials.get_token("nobody"))

    def test_saving_again_replaces_the_previous_token(self):
        credentials.save_token("alice", "ghp_old")
        credentials.save_token("alice", "ghp_new")

        self.assertEqual(credentials.get_token("alice"), "ghp_new")

    def test_the_row_stored_on_disk_is_not_the_plaintext_token(self):
        credentials.save_token("alice", "ghp_alice_token")

        with database.get_db_connection() as conn:
            row = conn.execute(
                "SELECT encrypted_token FROM github_credentials WHERE user_id = ?", ("alice",)
            ).fetchone()

        self.assertNotIn("ghp_alice_token", row[0])

    def test_users_tokens_are_isolated(self):
        credentials.save_token("alice", "ghp_alice_token")
        credentials.save_token("bob", "ghp_bob_token")

        self.assertEqual(credentials.get_token("alice"), "ghp_alice_token")
        self.assertEqual(credentials.get_token("bob"), "ghp_bob_token")


class HasTokenTests(IsolatedDatabaseTestCase):
    def test_true_once_a_token_is_saved(self):
        self.assertFalse(credentials.has_token("alice"))
        credentials.save_token("alice", "ghp_alice_token")
        self.assertTrue(credentials.has_token("alice"))


class DeleteTokenTests(IsolatedDatabaseTestCase):
    def test_deleting_a_saved_token_removes_it(self):
        credentials.save_token("alice", "ghp_alice_token")

        self.assertTrue(credentials.delete_token("alice"))
        self.assertIsNone(credentials.get_token("alice"))

    def test_deleting_an_unknown_user_returns_false(self):
        self.assertFalse(credentials.delete_token("nobody"))

    def test_deleting_one_users_token_does_not_touch_another(self):
        credentials.save_token("alice", "ghp_alice_token")
        credentials.save_token("bob", "ghp_bob_token")

        credentials.delete_token("alice")

        self.assertIsNone(credentials.get_token("alice"))
        self.assertEqual(credentials.get_token("bob"), "ghp_bob_token")


if __name__ == "__main__":
    unittest.main()
