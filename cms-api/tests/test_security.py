"""Hashing real con credenciales exclusivamente ficticias; nunca imprimir hashes."""

import unittest

from app.core.security import PasswordHasher, hash_password, verify_password


class PasswordHasherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "test-password"
        cls.first = hash_password(cls.password)
        cls.second = hash_password(cls.password)

    def test_hash_is_text_and_is_not_the_plain_password(self):
        self.assertIsInstance(self.first, str)
        self.assertTrue(self.first != self.password)

    def test_hash_uses_argon2id(self):
        self.assertTrue(self.first.startswith("$argon2id$"))

    def test_correct_password_verifies(self):
        self.assertIs(verify_password(self.password, self.first), True)

    def test_incorrect_password_does_not_verify(self):
        self.assertIs(verify_password("incorrect-fixture", self.first), False)

    def test_independent_hashes_have_different_salts(self):
        self.assertTrue(self.first != self.second)
        self.assertTrue(self.first.split("$")[4] != self.second.split("$")[4])

    def test_both_hashes_verify_the_original_password(self):
        self.assertTrue(all(verify_password(self.password, h) for h in (self.first, self.second)))

    def test_unknown_and_malformed_hashes_return_false(self):
        for value in ("", "not-a-hash", "$argon2id$v=19$m=65536,t=3,p=4$invalid$invalid"):
            with self.subTest(case="invalid fixture"):
                self.assertIs(verify_password(self.password, value), False)
        self.assertIs(verify_password("\ud800", self.first), False)

    def test_hasher_requires_text_and_verification_handles_wrong_types(self):
        with self.assertRaises(TypeError):
            hash_password(b"fixture")
        self.assertFalse(verify_password(None, self.first))
        self.assertFalse(verify_password(self.password, None))

    def test_hashing_and_verification_do_not_log_credentials(self):
        with self.assertNoLogs():
            hasher = PasswordHasher()
            self.assertTrue(hasher.verify_password(self.password, hasher.hash_password(self.password)))
