"""Structural checks that do not connect to PostgreSQL."""

import unittest

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    String,
    UniqueConstraint,
    inspect,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from app.domain.enums import DocumentStatus
from app.infrastructure.database.base import Base
from app.infrastructure.database.models import (
    CanvasBlockModel,
    DocumentModel,
    ReviewReportModel,
    TemplateModel,
)


class DatabaseModelTests(unittest.TestCase):
    def test_metadata_contains_only_the_five_persistent_entities(self):
        self.assertEqual(
            set(Base.metadata.tables),
            {"templates", "documents", "canvas_blocks", "review_reports", "admin_users"},
        )
        expected_columns = {
            "templates": {
                "template_id", "name", "target_type", "is_default",
                "allow_published_edit", "metadata_contract", "layout_structure",
                "created_at",
            },
            "documents": {
                "document_id", "slug", "title", "content_type", "status",
                "template_id", "frozen_template", "metadata_values", "updated_at",
                "published_at",
            },
            "canvas_blocks": {
                "block_id", "document_id", "block_type", "order_index",
                "content_payload", "style_config",
            },
            "review_reports": {"report_id", "document_id", "findings", "audited_at"},
            "admin_users": {
                "user_id", "username", "password_hash", "is_active",
                "created_at", "updated_at", "last_login_at",
            },
        }
        for table_name, names in expected_columns.items():
            with self.subTest(table=table_name):
                self.assertEqual(set(Base.metadata.tables[table_name].columns.keys()), names)

    def test_identifiers_are_uuid_without_implicit_generation(self):
        identifiers = {
            "templates": "template_id",
            "documents": "document_id",
            "canvas_blocks": "block_id",
            "review_reports": "report_id",
        }
        for table_name, primary_key in identifiers.items():
            table = Base.metadata.tables[table_name]
            self.assertEqual([column.name for column in table.primary_key], [primary_key])
            for column in table.columns:
                if column.name.endswith("_id"):
                    with self.subTest(table=table_name, column=column.name):
                        self.assertIsInstance(column.type, UUID)
                        self.assertTrue(column.type.as_uuid)
                        self.assertIsNone(column.default)
                        self.assertIsNone(column.server_default)

    def test_nullability_matches_the_structural_contract(self):
        nullable = {
            "templates": set(),
            "documents": {"frozen_template", "metadata_values", "published_at"},
            "canvas_blocks": {"style_config"},
            "review_reports": set(),
        }
        for table_name, nullable_names in nullable.items():
            for column in Base.metadata.tables[table_name].columns:
                with self.subTest(table=table_name, column=column.name):
                    self.assertEqual(column.nullable, column.name in nullable_names)

    def test_unique_keys_protect_resource_names_and_block_positions(self):
        expected = {
            "templates": {("name",)},
            "documents": {("slug",)},
            "canvas_blocks": {("document_id", "order_index")},
        }
        for table_name, required in expected.items():
            table = Base.metadata.tables[table_name]
            unique_keys = {
                tuple(column.name for column in constraint.columns)
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            }
            unique_keys.update(
                tuple(column.name for column in index.columns)
                for index in table.indexes if index.unique
            )
            with self.subTest(table=table_name):
                self.assertTrue(required.issubset(unique_keys))

    def test_foreign_keys_protect_templates_and_compose_document_children(self):
        expected = {
            "documents": ("template_id", "templates.template_id", "RESTRICT"),
            "canvas_blocks": ("document_id", "documents.document_id", "CASCADE"),
            "review_reports": ("document_id", "documents.document_id", "CASCADE"),
        }
        for table_name, (local_name, target, ondelete) in expected.items():
            foreign_keys = list(Base.metadata.tables[table_name].foreign_keys)
            with self.subTest(table=table_name):
                self.assertEqual(len(foreign_keys), 1)
                self.assertEqual(foreign_keys[0].parent.name, local_name)
                self.assertEqual(foreign_keys[0].target_fullname, target)
                self.assertEqual(foreign_keys[0].ondelete, ondelete)

    def test_contractual_objects_use_jsonb(self):
        expected = {
            "templates": {"metadata_contract", "layout_structure"},
            "documents": {"frozen_template", "metadata_values"},
            "canvas_blocks": {"content_payload", "style_config"},
            "review_reports": {"findings"},
        }
        for table_name, names in expected.items():
            for name in names:
                with self.subTest(table=table_name, column=name):
                    self.assertIsInstance(Base.metadata.tables[table_name].c[name].type, JSONB)

    def test_timestamps_have_timezone_and_no_implicit_clock(self):
        timestamps = {
            "templates": {"created_at"},
            "documents": {"updated_at", "published_at"},
            "review_reports": {"audited_at"},
        }
        for table_name, names in timestamps.items():
            for name in names:
                column = Base.metadata.tables[table_name].c[name]
                with self.subTest(table=table_name, column=name):
                    self.assertIsInstance(column.type, DateTime)
                    self.assertTrue(column.type.timezone)
                    self.assertIsNone(column.default)
                    self.assertIsNone(column.server_default)

    def test_only_document_status_is_a_closed_vocabulary(self):
        expected_statuses = {status.value for status in DocumentStatus}
        self.assertEqual(
            expected_statuses, {"BORRADOR", "EN_REVISION", "PUBLICADO", "ARCHIVADO"}
        )
        documents = Base.metadata.tables["documents"]
        status_type = documents.c.status.type
        self.assertIsInstance(status_type, String)
        if isinstance(status_type, Enum):
            self.assertFalse(status_type.native_enum)
            self.assertEqual(set(status_type.enums), expected_statuses)
        checks = " ".join(
            str(constraint.sqltext.compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            ))
            for constraint in documents.constraints
            if isinstance(constraint, CheckConstraint)
        )
        self.assertIn("status", checks)
        for status in expected_statuses:
            self.assertIn(f"'{status}'", checks)
        for table_name, column_name in (
            ("templates", "target_type"),
            ("documents", "content_type"),
            ("canvas_blocks", "block_type"),
        ):
            table = Base.metadata.tables[table_name]
            with self.subTest(table=table_name, column=column_name):
                self.assertIsInstance(table.c[column_name].type, String)
                self.assertNotIsInstance(table.c[column_name].type, Enum)
                self.assertFalse(any(
                    column_name in str(constraint.sqltext)
                    for constraint in table.constraints
                    if isinstance(constraint, CheckConstraint)
                ))
        self.assertIsInstance(Base.metadata.tables["canvas_blocks"].c.order_index.type, Integer)

    def test_indexes_support_foreign_key_status_and_latest_review_queries(self):
        documents = Base.metadata.tables["documents"]
        indexed_columns = {tuple(column.name for column in index.columns) for index in documents.indexes}
        self.assertIn(("template_id",), indexed_columns)
        self.assertIn(("status",), indexed_columns)
        reviews = Base.metadata.tables["review_reports"]
        self.assertTrue(any(
            tuple(column.name for column in index.columns) == ("document_id", "audited_at")
            for index in reviews.indexes
        ))

    def test_relationship_mappers_are_bidirectional_and_blocks_are_ordered(self):
        configure_mappers()
        for parent, name, child, reverse in (
            (TemplateModel, "documents", DocumentModel, "template"),
            (DocumentModel, "canvas_blocks", CanvasBlockModel, "document"),
            (DocumentModel, "review_reports", ReviewReportModel, "document"),
        ):
            relationship = inspect(parent).relationships[name]
            with self.subTest(relationship=name):
                self.assertIs(relationship.mapper.class_, child)
                self.assertEqual(relationship.back_populates, reverse)
                self.assertTrue(relationship.uselist)
                self.assertIs(inspect(child).relationships[reverse].mapper.class_, parent)
        ordering = inspect(DocumentModel).relationships.canvas_blocks.order_by
        self.assertEqual(len(ordering), 1)
        self.assertTrue(ordering[0].compare(CanvasBlockModel.order_index.expression))

    def test_postgresql_ddl_compiles_without_extra_state_or_uuid_defaults(self):
        ddl = "\n".join(
            str(CreateTable(table).compile(dialect=postgresql.dialect()))
            for table in Base.metadata.sorted_tables
        )
        self.assertIn("JSONB", ddl)
        self.assertIn("TIMESTAMP WITH TIME ZONE", ddl)
        self.assertIn("UUID", ddl)
        self.assertIn("ON DELETE RESTRICT", ddl)
        self.assertEqual(ddl.count("ON DELETE CASCADE"), 2)
        self.assertNotIn("latest_review", ddl)
        self.assertNotIn("SERIAL", ddl)
        self.assertNotIn("gen_random_uuid", ddl)
        self.assertNotIn("uuid_generate", ddl)


if __name__ == "__main__":
    unittest.main()
