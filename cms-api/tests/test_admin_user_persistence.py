"""Integración administrativa opt-in: fixtures transaccionales, sin credenciales."""

from datetime import datetime, timedelta, timezone
import unittest
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database.models import AdminUserModel
from tests.postgresql import IsolatedAdminPostgreSQLTestCase


USER_ID = UUID("0195e4f0-0000-7000-8000-000000000101")
SECOND_USER_ID = UUID("0195e4f0-0000-7000-8000-000000000102")
TIMESTAMP = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
# Opaque storage fixture, deliberately not a usable Argon2 hash or login credential.
HASH_FIXTURE = "$argon2id$storage-test-fixture-only"


class AdminUserPersistenceTests(IsolatedAdminPostgreSQLTestCase):
    def _admin(self, *, user_id=USER_ID, username="admin-persistence-test"):
        admin = AdminUserModel(
            user_id=user_id,
            username=username,
            password_hash=HASH_FIXTURE,
            created_at=TIMESTAMP,
            updated_at=TIMESTAMP,
        )
        self.session.add(admin)
        return admin

    def test_valid_admin_can_be_inserted_and_reloaded(self):
        self._admin()
        self.session.flush()
        self.session.expire_all()
        admin = self.session.get(AdminUserModel, USER_ID)
        self.assertEqual(admin.username, "admin-persistence-test")
        self.assertEqual(admin.user_id.version, 7)
        self.assertIs(admin.is_active, True)
        self.assertEqual(admin.created_at, TIMESTAMP)

    def test_duplicate_username_is_rejected(self):
        self._admin()
        self.session.flush()
        self._admin(user_id=SECOND_USER_ID)
        try:
            with self.assertRaises(IntegrityError) as raised:
                self.session.flush()
            self.assertEqual(raised.exception.orig.sqlstate, "23505")
        finally:
            self.session.rollback()

    def test_password_hash_round_trips_as_a_string(self):
        self._admin()
        self.session.flush()
        self.session.expire_all()
        stored = self.session.get(AdminUserModel, USER_ID).password_hash
        self.assertIsInstance(stored, str)
        self.assertEqual(stored, HASH_FIXTURE)

    def test_last_login_at_is_initially_null(self):
        self._admin()
        self.session.flush()
        self.session.expire_all()
        self.assertIsNone(self.session.get(AdminUserModel, USER_ID).last_login_at)

    def test_an_admin_can_be_deactivated_without_deleting_it(self):
        admin = self._admin()
        self.session.flush()
        admin.is_active = False
        admin.updated_at = TIMESTAMP + timedelta(minutes=1)
        self.session.flush()
        self.session.expire_all()
        stored = self.session.get(AdminUserModel, USER_ID)
        self.assertIsNotNone(stored)
        self.assertIs(stored.is_active, False)
        self.assertEqual(stored.updated_at, TIMESTAMP + timedelta(minutes=1))

    def test_database_defaults_apply_to_inserts_without_orm_defaults(self):
        row = self.session.execute(text(
            "INSERT INTO admin_users "
            "(user_id, username, password_hash, created_at, updated_at) "
            "VALUES (:user_id, :username, :password_hash, :created_at, :updated_at) "
            "RETURNING is_active, last_login_at"
        ), {
            "user_id": USER_ID,
            "username": "admin-database-default-test",
            "password_hash": HASH_FIXTURE,
            "created_at": TIMESTAMP,
            "updated_at": TIMESTAMP,
        }).one()
        self.assertIs(row.is_active, True)
        self.assertIsNone(row.last_login_at)


if __name__ == "__main__":
    unittest.main()
