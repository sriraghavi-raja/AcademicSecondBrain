import unittest
from unittest.mock import patch

from src.rag.security.crypto import EncryptionKeyMissing, decrypt, encrypt

TEST_KEY = "1t-C8yRopRF0MVMT3b98otEVP3C2zopFd_KjgEIwEk4="


class EncryptDecryptTests(unittest.TestCase):
    def test_decrypting_an_encrypted_value_returns_the_original(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN_ENCRYPTION_KEY": TEST_KEY}):
            ciphertext = encrypt("ghp_supersecrettoken")
            self.assertEqual(decrypt(ciphertext), "ghp_supersecrettoken")

    def test_the_stored_ciphertext_does_not_contain_the_plaintext(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN_ENCRYPTION_KEY": TEST_KEY}):
            ciphertext = encrypt("ghp_supersecrettoken")
            self.assertNotIn("ghp_supersecrettoken", ciphertext)

    def test_encrypting_without_a_configured_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(EncryptionKeyMissing):
                encrypt("ghp_supersecrettoken")

    def test_decrypting_without_a_configured_key_raises(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN_ENCRYPTION_KEY": TEST_KEY}):
            ciphertext = encrypt("ghp_supersecrettoken")
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(EncryptionKeyMissing):
                decrypt(ciphertext)


if __name__ == "__main__":
    unittest.main()
