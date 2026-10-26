"""HTTP y repositorio reales sobre pg_temp; nunca se autentica al administrador real."""

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies.auth import get_auth_service
from app.core.config import get_settings
from app.core.jwt import create_access_token, decode_access_token
from app.core.security import verify_password
from app.infrastructure.database.admin_user_repository import SQLAlchemyAdminUserRepository
from app.infrastructure.database.models import AdminUserModel
from app.infrastructure.database.session import get_session
from app.main import app
from tests.auth_support import (
    AUTH_MISSING_ID, AUTH_PASSWORD, AUTH_USER_ID, AUTH_USERNAME, FIXTURE_TIME,
    AuthPostgreSQLTestCase, auth_settings, signed_fixture_token,
)


class AuthHTTPTestCase(AuthPostgreSQLTestCase):
    def setUp(self):
        super().setUp()
        previous = app.dependency_overrides.copy()

        def restore():
            app.dependency_overrides.clear()
            app.dependency_overrides.update(previous)

        self.addCleanup(restore)

        def isolated_session():
            with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_session] = isolated_session
        app.dependency_overrides[get_auth_service] = lambda: self.service
        app.dependency_overrides[get_settings] = lambda: self.settings
        self.client = self.enterContext(TestClient(app))

    def login(self, username=AUTH_USERNAME, password=AUTH_PASSWORD):
        return self.client.post("/api/v1/auth/login", json={"username": username, "password": password})

    def current(self, token):
        return self.client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})

    def last_login(self):
        return self.connection.scalar(select(AdminUserModel.last_login_at).where(AdminUserModel.user_id == AUTH_USER_ID))

    def assert_invalid_token(self, response):
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")
        self.assertEqual(response.json(), {"detail": "No se pudieron validar las credenciales."})


class LoginHTTPTests(AuthHTTPTestCase):
    def test_valid_json_credentials_return_200_without_bearer_header(self):
        self.assertEqual(self.login().status_code, 200)

    def test_response_has_only_access_token_type_and_expiry(self):
        response = self.login()
        self.assertEqual(set(response.json()), {"access_token", "token_type", "expires_in"})
        self.assertEqual(decode_access_token(response.json()["access_token"], settings=self.settings), AUTH_USER_ID)

    def test_token_type_is_bearer(self):
        self.assertEqual(self.login().json()["token_type"], "bearer")

    def test_default_expiry_is_1800_seconds(self):
        self.assertEqual(self.login().json()["expires_in"], 1800)

    def test_configured_expiry_is_used(self):
        self.settings = auth_settings(jwt_access_token_expire_minutes=7)
        self.assertEqual(self.login().json()["expires_in"], 420)

    def test_wrong_password_returns_generic_401_and_does_not_update_login(self):
        response = self.login(password="incorrect-fixture")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Credenciales inválidas."})
        self.assertIsNone(self.last_login())

    def test_unknown_username_returns_generic_401(self):
        response = self.login(username="missing-auth-fixture")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Credenciales inválidas."})
        self.assertIsNone(self.last_login())

    def test_inactive_user_returns_same_generic_401(self):
        self.connection.execute(update(AdminUserModel).values(is_active=False))
        response = self.login()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Credenciales inválidas."})
        self.assertIsNone(self.last_login())

    def test_deactivation_during_password_verification_prevents_token_and_login_update(self):
        def verify_then_deactivate(password, password_hash):
            matches = verify_password(password, password_hash)
            # Reproduce el estado que encuentra el UPDATE si otra transacción
            # desactiva la cuenta durante Argon2, dentro del aislamiento pg_temp.
            self.connection.execute(
                update(AdminUserModel).where(AdminUserModel.user_id == AUTH_USER_ID).values(is_active=False)
            )
            return matches

        with patch("app.services.auth_service.verify_password", side_effect=verify_then_deactivate), patch(
            "app.api.v1.endpoints.auth.create_access_token"
        ) as create_token:
            response = self.login()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Credenciales inválidas."})
        self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")
        self.assertIsNone(self.last_login())
        create_token.assert_not_called()

    def test_unknown_wrong_password_and_inactive_responses_are_identical(self):
        wrong = self.login(password="incorrect-fixture")
        missing = self.login(username="missing-auth-fixture")
        self.connection.execute(update(AdminUserModel).values(is_active=False))
        inactive = self.login()
        for response in (missing, inactive):
            self.assertEqual(response.status_code, wrong.status_code)
            self.assertEqual(response.content, wrong.content)
            self.assertEqual(response.headers.get("WWW-Authenticate"), wrong.headers.get("WWW-Authenticate"))

    def test_failure_contains_www_authenticate_bearer(self):
        self.assertEqual(self.login(password="incorrect-fixture").headers.get("WWW-Authenticate"), "Bearer")

    def test_response_contains_no_password_or_hash(self):
        response = self.login()
        self.assertNotIn("password_hash", response.json())
        self.assertNotIn("password", response.json())
        self.assertTrue(AUTH_PASSWORD not in response.text)

    def test_success_updates_only_last_login_with_aware_utc_timestamp(self):
        before = datetime.now(timezone.utc)
        self.assertEqual(self.login(username="  " + AUTH_USERNAME + "  ").status_code, 200)
        row = self.connection.execute(select(AdminUserModel.__table__)).mappings().one()
        self.assertTrue(before <= row["last_login_at"] <= datetime.now(timezone.utc))
        self.assertIsNotNone(row["last_login_at"].utcoffset())
        self.assertEqual(row["created_at"], FIXTURE_TIME)
        self.assertEqual(row["updated_at"], FIXTURE_TIME)
        self.assertEqual(row["username"], AUTH_USERNAME)

    def test_database_failure_rolls_back_and_does_not_issue_token(self):
        original = SQLAlchemyAdminUserRepository.update_last_login

        def fail_after_write(repository, user_id, timestamp):
            original(repository, user_id, timestamp)
            raise SQLAlchemyError("internal-auth-fixture-detail")

        with patch.object(SQLAlchemyAdminUserRepository, "update_last_login", fail_after_write), patch(
            "app.api.v1.endpoints.auth.create_access_token"
        ) as create_token:
            response = self.login()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("internal-auth-fixture-detail", response.text)
        self.assertNotIn("access_token", response.json())
        self.assertIsNone(self.last_login())
        create_token.assert_not_called()

    def test_validation_failures_do_not_echo_password_or_body(self):
        cases = [
            {"password": AUTH_PASSWORD},
            {"username": 123, "password": AUTH_PASSWORD},
            {"username": AUTH_USERNAME, "password": {"nested": AUTH_PASSWORD}},
            {"username": AUTH_USERNAME, "password": AUTH_PASSWORD, "extra": AUTH_PASSWORD},
        ]
        for body in cases:
            response = self.client.post("/api/v1/auth/login", json=body)
            self.assertEqual(response.status_code, 422)
            self.assertTrue(AUTH_PASSWORD not in response.text)
        response = self.client.post("/api/v1/auth/login", content='{"password":"' + AUTH_PASSWORD, headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)
        self.assertTrue(AUTH_PASSWORD not in response.text)

    def test_form_encoded_login_is_not_accepted(self):
        response = self.client.post("/api/v1/auth/login", data={"username": AUTH_USERNAME, "password": AUTH_PASSWORD})
        self.assertEqual(response.status_code, 422)
        self.assertTrue(AUTH_PASSWORD not in response.text)

    def test_login_and_me_do_not_log_credentials_or_tokens(self):
        with self.assertNoLogs("app", level="DEBUG"):
            response = self.login()
            self.assertEqual(self.current(response.json()["access_token"]).status_code, 200)


class CurrentAdminHTTPTests(AuthHTTPTestCase):
    def test_valid_token_returns_200(self):
        self.assertEqual(self.current(create_access_token(AUTH_USER_ID, settings=self.settings)).status_code, 200)

    def test_response_has_exactly_the_three_public_fields(self):
        response = self.current(signed_fixture_token())
        self.assertEqual(response.json(), {"user_id": str(AUTH_USER_ID), "username": AUTH_USERNAME, "is_active": True})

    def test_response_does_not_contain_password_hash_or_token(self):
        token = signed_fixture_token()
        response = self.current(token)
        for field in ("password", "password_hash", "access_token", "jwt_secret_key", "database_url"):
            self.assertNotIn(field, response.json())
        self.assertTrue(token not in response.text)

    def test_missing_token_returns_401(self):
        self.assert_invalid_token(self.client.get("/api/v1/auth/me"))

    def test_random_token_returns_401(self):
        self.assert_invalid_token(self.current("random-fixture"))

    def test_altered_token_returns_401(self):
        head, payload, signature = signed_fixture_token().split(".")
        altered = head + "." + payload + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
        self.assert_invalid_token(self.current(altered))

    def test_expired_token_returns_401(self):
        now = int(datetime.now(timezone.utc).timestamp())
        self.assert_invalid_token(self.current(signed_fixture_token(iat=now - 120, exp=now - 60)))

    def test_non_uuid_subject_returns_401(self):
        self.assert_invalid_token(self.current(signed_fixture_token(sub="invalid-fixture-subject")))

    def test_missing_user_returns_401(self):
        self.assert_invalid_token(self.current(signed_fixture_token(sub=str(AUTH_MISSING_ID))))

    def test_user_deactivated_after_token_issue_returns_403(self):
        token = signed_fixture_token()
        self.connection.execute(update(AdminUserModel).values(is_active=False))
        response = self.current(token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Cuenta inactiva."})

    def test_wrong_signature_returns_401(self):
        self.assert_invalid_token(self.current(signed_fixture_token(secret="wrong-fixture-signing-secret-" * 3)))

    def test_wrong_type_and_disallowed_algorithms_return_401(self):
        for token in (signed_fixture_token(type="refresh"), signed_fixture_token(algorithm="none"), signed_fixture_token(algorithm="HS512")):
            self.assert_invalid_token(self.current(token))

    def test_wrong_authorization_scheme_or_empty_bearer_returns_401(self):
        for header in ("Basic fixture", "Bearer", "Bearer "):
            self.assert_invalid_token(self.client.get("/api/v1/auth/me", headers={"Authorization": header}))

    def test_me_does_not_change_last_login(self):
        self.assertEqual(self.current(signed_fixture_token()).status_code, 200)
        self.assertIsNone(self.last_login())


class AuthRepositoryTests(AuthPostgreSQLTestCase):
    def test_get_by_id_reads_fixture_and_returns_none_for_missing_user(self):
        repository = SQLAlchemyAdminUserRepository(self.session)
        self.assertEqual(repository.get_by_id(AUTH_USER_ID).username, AUTH_USERNAME)
        self.assertIsNone(repository.get_by_id(AUTH_MISSING_ID))

    def test_update_last_login_changes_no_other_columns(self):
        timestamp = datetime.now(timezone.utc)
        before = self.connection.execute(select(AdminUserModel.__table__)).mappings().one()
        repository = SQLAlchemyAdminUserRepository(self.session)
        self.assertTrue(repository.update_last_login(AUTH_USER_ID, timestamp))
        after = self.connection.execute(select(AdminUserModel.__table__)).mappings().one()
        self.assertTrue(all(before[key] == after[key] for key in before if key != "last_login_at"))
        self.assertEqual(after["last_login_at"], timestamp)

    def test_update_missing_user_returns_false(self):
        self.assertFalse(SQLAlchemyAdminUserRepository(self.session).update_last_login(AUTH_MISSING_ID, datetime.now(timezone.utc)))

    def test_update_inactive_user_returns_false_without_changing_last_login(self):
        self.connection.execute(update(AdminUserModel).where(AdminUserModel.user_id == AUTH_USER_ID).values(is_active=False))
        repository = SQLAlchemyAdminUserRepository(self.session)
        self.assertFalse(repository.update_last_login(AUTH_USER_ID, datetime.now(timezone.utc)))
        self.assertIsNone(self.connection.scalar(select(AdminUserModel.last_login_at).where(AdminUserModel.user_id == AUTH_USER_ID)))
