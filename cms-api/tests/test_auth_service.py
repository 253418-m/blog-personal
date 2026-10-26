"""Servicio unitario: persistencia simulada y verificación Argon2 real."""

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, Mock, patch

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.models import AdminUserModel
from app.repositories.admin_user import AdminUserRepository
from app.services.auth_service import AuthService, AuthenticationUnavailable, InvalidCredentials, _DUMMY_HASH
from tests.auth_support import AUTH_PASSWORD, AUTH_USER_ID, AUTH_USERNAME, FIXTURE_TIME, fixture_password_hash


class AuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock(spec=Session)
        self.session.__enter__.return_value = self.session
        self.repository = Mock(spec=AdminUserRepository)
        self.repository.update_last_login.return_value = True
        self.admin = AdminUserModel(
            user_id=AUTH_USER_ID, username=AUTH_USERNAME, password_hash=fixture_password_hash(),
            is_active=True, created_at=FIXTURE_TIME, updated_at=FIXTURE_TIME, last_login_at=None,
        )
        self.repository.get_by_username.return_value = self.admin
        self.repo_patch = patch("app.services.auth_service.SQLAlchemyAdminUserRepository", return_value=self.repository)
        self.repo_patch.start()
        self.addCleanup(self.repo_patch.stop)
        self.service = AuthService(lambda: self.session)

    def test_valid_credentials_authenticate(self):
        self.assertIs(self.service.authenticate(AUTH_USERNAME, AUTH_PASSWORD), self.admin)

    def test_username_outer_spaces_are_normalized(self):
        self.service.authenticate("  " + AUTH_USERNAME + "  ", AUTH_PASSWORD)
        self.repository.get_by_username.assert_called_once_with(AUTH_USERNAME)

    def test_wrong_password_fails_without_updating_last_login(self):
        with self.assertRaises(InvalidCredentials):
            self.service.authenticate(AUTH_USERNAME, "incorrect-fixture")
        self.repository.update_last_login.assert_not_called()

    def test_unknown_username_fails(self):
        self.repository.get_by_username.return_value = None
        with self.assertRaises(InvalidCredentials):
            self.service.authenticate("missing-fixture", AUTH_PASSWORD)
        self.repository.update_last_login.assert_not_called()

    def test_inactive_user_fails_without_updating_last_login(self):
        self.admin.is_active = False
        with self.assertRaises(InvalidCredentials):
            self.service.authenticate(AUTH_USERNAME, AUTH_PASSWORD)
        self.repository.update_last_login.assert_not_called()

    def test_success_updates_last_login_with_aware_utc_timestamp(self):
        before = datetime.now(timezone.utc)
        self.service.authenticate(AUTH_USERNAME, AUTH_PASSWORD)
        user_id, timestamp = self.repository.update_last_login.call_args.args
        self.assertEqual(user_id, AUTH_USER_ID)
        self.assertEqual(timestamp.tzinfo, timezone.utc)
        self.assertTrue(before <= timestamp <= datetime.now(timezone.utc))

    def test_missing_user_runs_real_dummy_verification(self):
        from app.core.security import verify_password

        self.repository.get_by_username.return_value = None
        with patch("app.services.auth_service.verify_password", wraps=verify_password) as verify:
            with self.assertRaises(InvalidCredentials):
                self.service.authenticate("missing-fixture", AUTH_PASSWORD)
        self.assertEqual(verify.call_count, 1)
        self.assertTrue(verify.call_args.args[1] == _DUMMY_HASH)
        self.assertTrue(_DUMMY_HASH.startswith("$argon2id$"))

    def test_storage_failure_is_safe_and_does_not_return_success(self):
        self.repository.update_last_login.side_effect = SQLAlchemyError("private-storage-detail")
        with self.assertRaises(AuthenticationUnavailable) as raised:
            self.service.authenticate(AUTH_USERNAME, AUTH_PASSWORD)
        self.assertNotIn("private-storage-detail", str(raised.exception))

    def test_commit_failure_does_not_return_authenticated_user(self):
        self.session.begin.return_value.__exit__.side_effect = SQLAlchemyError("private-commit-detail")
        with self.assertRaises(AuthenticationUnavailable):
            self.service.authenticate(AUTH_USERNAME, AUTH_PASSWORD)
