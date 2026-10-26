"""Backfill y reversión de 0003 exclusivamente sobre Documents temporales."""

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.test_templates import TemplateHTTPTestCase


class DocumentMigrationTests(TemplateHTTPTestCase):
    def setUp(self):
        super().setUp()
        path = Path(__file__).resolve().parents[1] / "alembic/versions/0003_simplify_documents.py"
        spec = importlib.util.spec_from_file_location("document_migration_fixture", path)
        self.migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.migration)

    def apply(self, operation):
        with Operations.context(MigrationContext.configure(self.connection)):
            operation()

    def test_backfill_preserves_historical_document(self):
        template = self.seed()
        self.add_document(template)
        self.connection.execute(text("ALTER TABLE pg_temp.documents DROP COLUMN content, DROP COLUMN created_at"))
        before = self.connection.execute(text("SELECT * FROM pg_temp.documents")).mappings().one()
        self.apply(self.migration.upgrade)
        after = dict(self.connection.execute(text("SELECT * FROM pg_temp.documents")).mappings().one())
        self.assertEqual(after.pop("content"), "")
        self.assertEqual(after.pop("created_at"), before["updated_at"])
        self.assertEqual(after, dict(before))

    def test_downgrade_refuses_to_discard_existing_documents(self):
        self.add_document(self.seed())
        before = self.connection.execute(text("SELECT * FROM pg_temp.documents")).mappings().all()
        with self.assertRaises(DBAPIError):
            with self.connection.begin_nested():
                self.apply(self.migration.downgrade)
        self.assertEqual(self.connection.execute(text("SELECT * FROM pg_temp.documents")).mappings().all(), before)

    def test_empty_downgrade_upgrade_preserves_template_and_foreign_key(self):
        self.seed()
        before = self.rows()
        self.apply(self.migration.downgrade)
        self.apply(self.migration.upgrade)
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.connection.scalar(text(
            "SELECT count(*) FROM pg_constraint WHERE conrelid='pg_temp.documents'::regclass AND contype='f'"
        )), 1)
