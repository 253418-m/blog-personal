"""Bootstrap contra PostgreSQL real, siempre dentro de una transacción revertida."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.cli.create_admin import main
from app.core.security import verify_password
from app.infrastructure.database.admin_user_repository import SQLAlchemyAdminUserRepository
from app.infrastructure.database.models import AdminUserModel
from app.services.admin_bootstrap import (
    AdminBootstrapService,
    BOOTSTRAP_LOCK_ID,
    BOOTSTRAP_LOCK_NAMESPACE,
    BootstrapAlreadyCompleted,
    BootstrapStorageError,
    BootstrapValidationError,
    MIN_PASSWORD_LENGTH,
    UsernameAlreadyExists,
)
from tests.postgresql import IsolatedAdminPostgreSQLTestCase


class AdminBootstrapTests(IsolatedAdminPostgreSQLTestCase):
    password = "test-password"
    username = "bootstrap-test-fixture"

    def setUp(self):
        super().setUp()
        self.service = AdminBootstrapService(lambda: Session(
            bind=self.connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ))

    def _create(self):
        return self.service.create_first_admin(self.username, self.password)

    def _stored(self):
        return self.connection.execute(select(AdminUserModel.__table__)).mappings().one()

    def _count(self):
        return self.connection.scalar(select(func.count()).select_from(AdminUserModel))

    def test_creates_first_admin_with_uuid7_trimmed_username_and_timestamps(self):
        before = datetime.now(timezone.utc)
        result = self.service.create_first_admin("  " + self.username + "  ", self.password)
        stored = self._stored()
        self.assertEqual(result.username, self.username)
        self.assertEqual(stored["username"], self.username)
        self.assertEqual(result.user_id.version, 7)
        self.assertEqual(stored["user_id"], result.user_id)
        self.assertEqual(stored["created_at"], stored["updated_at"])
        self.assertTrue(before <= stored["created_at"] <= datetime.now(timezone.utc))
        self.assertEqual(self._count(), 1)
        self.assertFalse(hasattr(result, "password_hash"))
        self.assertFalse(hasattr(result, "password"))

    def test_plain_password_is_not_persisted(self):
        self._create()
        self.assertTrue(self.password not in self._stored()["password_hash"])
        self.assertEqual(set(self._stored()), {
            "user_id", "username", "password_hash", "is_active",
            "created_at", "updated_at", "last_login_at",
        })

    def test_persisted_hash_is_argon2id_and_verifies(self):
        self._create()
        stored_hash = self._stored()["password_hash"]
        self.assertTrue(stored_hash.startswith("$argon2id$"))
        self.assertTrue(verify_password(self.password, stored_hash))

    def test_first_admin_is_active(self):
        self._create()
        self.assertIs(self._stored()["is_active"], True)

    def test_last_login_is_null(self):
        self._create()
        self.assertIsNone(self._stored()["last_login_at"])

    def test_duplicate_username_is_rejected_without_modifying_the_user(self):
        self._create()
        original = self._stored()["password_hash"]
        with self.assertRaises(UsernameAlreadyExists):
            self.service.create_first_admin(self.username, "different-test-fixture")
        self.assertEqual(self._count(), 1)
        self.assertTrue(self._stored()["password_hash"] == original)

    def test_second_bootstrap_with_another_username_is_rejected(self):
        self._create()
        with self.assertRaises(BootstrapAlreadyCompleted):
            self.service.create_first_admin("second-bootstrap-fixture", self.password)
        self.assertEqual(self._count(), 1)

    def test_cli_password_mismatch_does_not_create_a_user(self):
        with patch("builtins.input", return_value=self.username), patch(
            "app.cli.create_admin.getpass.getpass", side_effect=[self.password, "other-fixture"]
        ), redirect_stdout(StringIO()):
            self.assertEqual(main([], bootstrap=self.service.create_first_admin), 1)
        self.assertEqual(self._count(), 0)

    def test_empty_password_does_not_create_a_user(self):
        with self.assertRaises(BootstrapValidationError):
            self.service.create_first_admin(self.username, "")
        self.assertEqual(self._count(), 0)

    def test_empty_or_whitespace_username_does_not_create_a_user(self):
        for username in ("", "   "):
            with self.assertRaises(BootstrapValidationError):
                self.service.create_first_admin(username, self.password)
        self.assertEqual(self._count(), 0)

    def test_short_and_whitespace_passwords_are_rejected(self):
        for password in ("x" * (MIN_PASSWORD_LENGTH - 1), " " * MIN_PASSWORD_LENGTH):
            with self.assertRaises(BootstrapValidationError):
                self.service.create_first_admin(self.username, password)
        self.assertEqual(self._count(), 0)

    def test_password_at_minimum_length_is_accepted_without_composition_rules(self):
        password = "x" * MIN_PASSWORD_LENGTH
        self.service.create_first_admin(self.username, password)
        self.assertTrue(verify_password(password, self._stored()["password_hash"]))

    def test_password_spaces_are_preserved(self):
        password = "  " + self.password + "  "
        self.service.create_first_admin(self.username, password)
        self.assertTrue(verify_password(password, self._stored()["password_hash"]))
        self.assertFalse(verify_password(password.strip(), self._stored()["password_hash"]))

    def test_inactive_admin_still_prevents_another_bootstrap(self):
        self._create()
        self.connection.execute(update(AdminUserModel).values(is_active=False))
        with self.assertRaises(BootstrapAlreadyCompleted):
            self.service.create_first_admin("second-bootstrap-fixture", self.password)
        self.assertEqual(self._count(), 1)

    def test_storage_failure_after_flush_rolls_back_and_hides_database_details(self):
        original_create = SQLAlchemyAdminUserRepository.create

        def fail_after_flush(repository, admin):
            original_create(repository, admin)
            raise SQLAlchemyError("internal-storage-fixture-detail")

        with patch.object(SQLAlchemyAdminUserRepository, "create", fail_after_flush):
            with self.assertRaises(BootstrapStorageError) as raised:
                self._create()
        self.assertNotIn("internal-storage-fixture-detail", str(raised.exception))
        self.assertEqual(self._count(), 0)

    def test_bootstrap_holds_transaction_lock_against_competing_connections(self):
        self._create()
        with self.engine.connect() as competitor, competitor.begin():
            acquired = competitor.scalar(select(func.pg_try_advisory_xact_lock(
                BOOTSTRAP_LOCK_NAMESPACE, BOOTSTRAP_LOCK_ID
            )))
            self.assertIs(acquired, False)
        self.assertEqual(self._count(), 1)

    def test_repository_get_and_exists_use_the_same_session(self):
        self.assertFalse(SQLAlchemyAdminUserRepository(self.session).exists_by_username(self.username))
        self.assertIsNone(SQLAlchemyAdminUserRepository(self.session).get_by_username(self.username))
        # Close the reader's savepoint before starting the service's transaction.
        self.session.close()
        self._create()
        repository = SQLAlchemyAdminUserRepository(self.session)
        self.assertTrue(repository.exists_by_username(self.username))
        stored = repository.get_by_username(self.username)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.user_id.version, 7)

    def test_cli_success_never_outputs_password_or_hash(self):
        output = StringIO()
        with patch("builtins.input", return_value=self.username), patch(
            "app.cli.create_admin.getpass.getpass", side_effect=[self.password, self.password]
        ), redirect_stdout(output):
            self.assertEqual(main([], bootstrap=self.service.create_first_admin), 0)
        self.assertIn("Administrador creado correctamente.", output.getvalue())
        self.assertTrue(self.password not in output.getvalue())
        self.assertTrue(self._stored()["password_hash"] not in output.getvalue())
        self.assertEqual(self._count(), 1)
