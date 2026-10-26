"""JWT unitario con claves ficticias; no imprimir tokens ni firmas."""

from datetime import datetime, timezone
import unittest

import jwt

from app.core.jwt import InvalidAccessToken, create_access_token, decode_access_token
from tests.auth_support import AUTH_USER_ID, JWT_TEST_SECRET, auth_settings, signed_fixture_token


class AccessTokenTests(unittest.TestCase):
    def setUp(self):
        self.settings = auth_settings()

    def _claims(self):
        return jwt.decode(
            create_access_token(AUTH_USER_ID, settings=self.settings),
            JWT_TEST_SECRET, algorithms=["HS256"],
        )

    def test_create_returns_jwt_string(self):
        token = create_access_token(AUTH_USER_ID, settings=self.settings)
        self.assertIsInstance(token, str)
        self.assertEqual(len(token.split(".")), 3)

    def test_decode_returns_original_user_id(self):
        token = create_access_token(AUTH_USER_ID, settings=self.settings)
        self.assertEqual(decode_access_token(token, settings=self.settings), AUTH_USER_ID)

    def test_subject_is_uuid_not_username(self):
        self.assertEqual(self._claims()["sub"], str(AUTH_USER_ID))

    def test_type_is_access(self):
        self.assertEqual(self._claims()["type"], "access")

    def test_iat_is_utc_numeric_date(self):
        claims = self._claims()
        self.assertIs(type(claims["iat"]), int)
        self.assertLessEqual(abs(datetime.now(timezone.utc).timestamp() - claims["iat"]), 3)

    def test_exp_has_default_ttl(self):
        claims = self._claims()
        self.assertEqual(claims["exp"] - claims["iat"], 1800)

    def test_ttl_is_configurable(self):
        token = create_access_token(AUTH_USER_ID, settings=auth_settings(jwt_access_token_expire_minutes=7))
        claims = jwt.decode(token, JWT_TEST_SECRET, algorithms=["HS256"])
        self.assertEqual(claims["exp"] - claims["iat"], 420)

    def test_payload_contains_only_the_four_public_claims(self):
        self.assertEqual(set(self._claims()), {"sub", "iat", "exp", "type"})

    def test_expired_token_is_rejected(self):
        now = int(datetime.now(timezone.utc).timestamp())
        with self.assertRaises(InvalidAccessToken):
            decode_access_token(signed_fixture_token(iat=now - 120, exp=now - 60), settings=self.settings)

    def test_altered_token_is_rejected(self):
        token = signed_fixture_token()
        head, payload, signature = token.split(".")
        altered = head + "." + payload + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
        with self.assertRaises(InvalidAccessToken):
            decode_access_token(altered, settings=self.settings)

    def test_wrong_signing_secret_is_rejected(self):
        with self.assertRaises(InvalidAccessToken):
            decode_access_token(signed_fixture_token(secret="other-fictitious-signing-key-" * 3), settings=self.settings)

    def test_subject_must_be_a_uuid(self):
        with self.assertRaises(InvalidAccessToken):
            decode_access_token(signed_fixture_token(sub="username-fixture"), settings=self.settings)

    def test_all_required_claims_must_be_present(self):
        for field in ("sub", "iat", "exp", "type"):
            claims = self._claims()
            claims.pop(field)
            token = jwt.encode(claims, JWT_TEST_SECRET, algorithm="HS256")
            with self.subTest(claim=field), self.assertRaises(InvalidAccessToken):
                decode_access_token(token, settings=self.settings)

    def test_wrong_token_type_is_rejected(self):
        with self.assertRaises(InvalidAccessToken):
            decode_access_token(signed_fixture_token(type="refresh"), settings=self.settings)

    def test_none_algorithm_is_rejected(self):
        with self.assertRaises(InvalidAccessToken):
            decode_access_token(signed_fixture_token(algorithm="none"), settings=self.settings)

    def test_other_algorithm_is_rejected(self):
        with self.assertRaises(InvalidAccessToken):
            decode_access_token(signed_fixture_token(algorithm="HS512"), settings=self.settings)

    def test_random_and_truncated_tokens_are_rejected(self):
        for token in ("random-fixture", "", signed_fixture_token()[:-12]):
            with self.assertRaises(InvalidAccessToken):
                decode_access_token(token, settings=self.settings)

    def test_future_iat_and_invalid_dates_are_rejected(self):
        now = int(datetime.now(timezone.utc).timestamp())
        for values in ({"iat": now + 60}, {"iat": now, "exp": now}, {"exp": "invalid"}, {"iat": []}, {"exp": True}):
            with self.subTest(case="invalid numeric dates"), self.assertRaises(InvalidAccessToken):
                decode_access_token(signed_fixture_token(**values), settings=self.settings)
