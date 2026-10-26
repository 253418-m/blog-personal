"""Contrato estructural de AdminUser y migración incremental, sin PostgreSQL."""

import os
from pathlib import Path
import subprocess
import sys
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.schema import CreateTable

from app.infrastructure.database.base import Base
from app.infrastructure.database.models import AdminUserModel


class AdminUserModelTests(unittest.TestCase):
    def setUp(self):
        self.table = AdminUserModel.__table__

    def test_admin_users_is_registered_with_exactly_the_contractual_columns(self):
        self.assertIs(Base.metadata.tables["admin_users"], self.table)
        self.assertEqual(set(self.table.c.keys()), {
            "user_id", "username", "password_hash", "is_active",
            "created_at", "updated_at", "last_login_at",
        })

    def test_user_id_is_a_required_uuid_primary_key_without_generation(self):
        column = self.table.c.user_id
        self.assertEqual(list(self.table.primary_key.columns), [column])
        self.assertFalse(column.nullable)
        self.assertIsInstance(column.type, UUID)
        self.assertTrue(column.type.as_uuid)
        self.assertIsNone(column.default)
        self.assertIsNone(column.server_default)

    def test_username_is_required_varchar_without_an_arbitrary_length(self):
        self.assertFalse(self.table.c.username.nullable)
        self.assertIsInstance(self.table.c.username.type, String)
        self.assertIsNone(self.table.c.username.type.length)

    def test_username_has_a_named_unique_constraint(self):
        self.assertTrue(any(
            isinstance(constraint, UniqueConstraint)
            and tuple(constraint.columns.keys()) == ("username",)
            and constraint.name == "uq_admin_users_username"
            for constraint in self.table.constraints
        ))

    def test_password_hash_is_required_text(self):
        self.assertFalse(self.table.c.password_hash.nullable)
        self.assertIsInstance(self.table.c.password_hash.type, Text)

    def test_no_password_column_exists(self):
        self.assertNotIn("password", self.table.c)

    def test_no_plain_password_column_exists(self):
        self.assertNotIn("plain_password", self.table.c)

    def test_is_active_is_a_required_boolean(self):
        self.assertFalse(self.table.c.is_active.nullable)
        self.assertIsInstance(self.table.c.is_active.type, Boolean)

    def test_is_active_defaults_to_true_in_orm_and_postgresql(self):
        column = self.table.c.is_active
        self.assertIs(column.default.arg, True)
        self.assertEqual(
            str(column.server_default.arg.compile(dialect=postgresql.dialect())),
            "true",
        )

    def test_last_login_at_allows_null_without_an_automatic_timestamp(self):
        column = self.table.c.last_login_at
        self.assertTrue(column.nullable)
        self.assertIsNone(column.default)
        self.assertIsNone(column.server_default)

    def test_all_timestamps_support_timezone_and_are_application_supplied(self):
        for name in ("created_at", "updated_at", "last_login_at"):
            column = self.table.c[name]
            with self.subTest(column=name):
                self.assertIsInstance(column.type, DateTime)
                self.assertTrue(column.type.timezone)
                self.assertIsNone(column.default)
                self.assertIsNone(column.server_default)
                self.assertEqual(column.nullable, name == "last_login_at")

    def test_admin_user_has_no_foreign_keys_or_relationships(self):
        self.assertFalse(self.table.foreign_keys)
        self.assertFalse(inspect(AdminUserModel).relationships)


class AdminUserMigrationTests(unittest.TestCase):
    backend_root = Path(__file__).resolve().parents[1]

    def _offline_sql(self, direction, revision_range):
        environment = os.environ.copy()
        # No credentials or connection: this destination is used only for DDL generation.
        environment["DATABASE_URL"] = "postgresql+psycopg://offline@localhost/cms_core"
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(self.backend_root / "alembic.ini"),
             direction, revision_range, "--sql"],
            cwd=self.backend_root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_alembic_has_one_head_and_preserves_the_initial_revision(self):
        script = ScriptDirectory.from_config(Config(str(self.backend_root / "alembic.ini")))
        self.assertEqual(script.get_heads(), ["0003_simplify_documents"])
        self.assertEqual(script.get_revision("0003_simplify_documents").down_revision, "0002_add_admin_users")
        self.assertEqual(
            script.get_revision("0002_add_admin_users").down_revision,
            "0001_initial_cms_schema",
        )
        self.assertIsNone(script.get_revision("0001_initial_cms_schema").down_revision)

    def test_incremental_upgrade_creates_only_admin_users_and_matches_orm_ddl(self):
        sql = self._offline_sql("upgrade", "0001_initial_cms_schema:0002_add_admin_users")
        self.assertEqual(sql.count("CREATE TABLE "), 1)
        self.assertIn("CREATE TABLE admin_users", sql)
        self.assertNotIn("ALTER TABLE", sql)
        self.assertNotIn("DROP TABLE", sql)
        self.assertNotIn("INSERT INTO", sql)
        expected = str(CreateTable(AdminUserModel.__table__).compile(dialect=postgresql.dialect()))
        self.assertIn(" ".join(expected.split()), " ".join(sql.split()))
        for table in ("templates", "documents", "canvas_blocks", "review_reports"):
            self.assertNotIn("CREATE TABLE " + table, sql)

    def test_incremental_downgrade_drops_only_admin_users(self):
        sql = self._offline_sql("downgrade", "0002_add_admin_users:0001_initial_cms_schema")
        self.assertEqual(sql.count("DROP TABLE "), 1)
        self.assertIn("DROP TABLE admin_users;", sql)
        self.assertNotIn("CREATE TABLE", sql)
        self.assertNotIn("ALTER TABLE", sql)
        for table in ("templates", "documents", "canvas_blocks", "review_reports"):
            self.assertNotIn("DROP TABLE " + table, sql)


if __name__ == "__main__":
    unittest.main()
