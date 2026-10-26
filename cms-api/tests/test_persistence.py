"""Opt-in PostgreSQL integration tests against the local migrated cms_core DB.

Set TEST_DATABASE_URL explicitly after running Alembic. Every test uses a
rollback-only outer transaction; no schema or persistent fixtures are created.
"""

from datetime import datetime, timedelta, timezone
import unittest
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.domain.enums import DocumentStatus
from app.infrastructure.database.models import (
    CanvasBlockModel,
    DocumentModel,
    ReviewReportModel,
    TemplateModel,
)
from tests.postgresql import PostgreSQLTestCase


# Explicit UUIDv7 test identifiers; generation belongs to future application cases.
TEMPLATE_ID = UUID("0195e4f0-0000-7000-8000-000000000001")
SECOND_TEMPLATE_ID = UUID("0195e4f0-0000-7000-8000-000000000002")
DOCUMENT_ID = UUID("0195e4f0-0000-7000-8000-000000000003")
SECOND_DOCUMENT_ID = UUID("0195e4f0-0000-7000-8000-000000000004")
BLOCK_ID = UUID("0195e4f0-0000-7000-8000-000000000005")
SECOND_BLOCK_ID = UUID("0195e4f0-0000-7000-8000-000000000006")
REPORT_ID = UUID("0195e4f0-0000-7000-8000-000000000007")
SECOND_REPORT_ID = UUID("0195e4f0-0000-7000-8000-000000000008")
MISSING_ID = UUID("0195e4f0-0000-7000-8000-0000000000ff")
TIMESTAMP = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


class PostgreSQLPersistenceTests(PostgreSQLTestCase):

    def _template(self, *, template_id=TEMPLATE_ID, name="Persistence test template", is_default=True):
        template = TemplateModel(
            template_id=template_id,
            name=name,
            target_type="DEV_BLOG",
            is_default=is_default,
            allow_published_edit=False,
            metadata_contract={"contract_test": {"fixture": True}},
            layout_structure={"contract_test_structure": ["fixture"]},
            created_at=TIMESTAMP,
        )
        self.session.add(template)
        return template

    def _document(self, template, *, document_id=DOCUMENT_ID, slug="persistence-test-document"):
        document = DocumentModel(
            document_id=document_id,
            slug=slug,
            title="Persistence test document",
            content_type="DEV_BLOG",
            status=DocumentStatus.BORRADOR,
            template=template,
            frozen_template=None,
            metadata_values=None,
            updated_at=TIMESTAMP,
            published_at=None,
        )
        self.session.add(document)
        return document

    def _block(self, document, *, block_id=BLOCK_ID, order_index=0):
        block = CanvasBlockModel(
            block_id=block_id,
            document=document,
            block_type="contract-test-block",  # Fixture value, not a proposed enum member.
            order_index=order_index,
            content_payload={"contract_test_content": "fixture"},
            style_config=None,
        )
        self.session.add(block)
        return block

    def _review(self, document, *, report_id=REPORT_ID, audited_at=TIMESTAMP):
        report = ReviewReportModel(
            report_id=report_id,
            document=document,
            findings={"contract_test_findings": []},
            audited_at=audited_at,
        )
        self.session.add(report)
        return report

    def _assert_flush_rejected(self, sqlstate):
        try:
            with self.assertRaises(IntegrityError) as raised:
                self.session.flush()
            self.assertEqual(raised.exception.orig.sqlstate, sqlstate)
        finally:
            self.session.rollback()

    def test_template_name_must_be_unique(self):
        self._template()
        self.session.flush()
        self._template(template_id=SECOND_TEMPLATE_ID, is_default=False)
        self._assert_flush_rejected("23505")

    def test_document_slug_must_be_unique(self):
        template = self._template()
        self._document(template)
        self.session.flush()
        self._document(template, document_id=SECOND_DOCUMENT_ID)
        self._assert_flush_rejected("23505")

    def test_document_requires_an_existing_template(self):
        self.session.add(DocumentModel(
            document_id=DOCUMENT_ID,
            slug="persistence-test-orphan-document",
            title="Orphan test fixture",
            content_type="DEV_BLOG",
            status=DocumentStatus.BORRADOR,
            template_id=MISSING_ID,
            updated_at=TIMESTAMP,
        ))
        self._assert_flush_rejected("23503")

    def test_canvas_block_requires_an_existing_document(self):
        self.session.add(CanvasBlockModel(
            block_id=BLOCK_ID,
            document_id=MISSING_ID,
            block_type="contract-test-block",
            order_index=0,
            content_payload={"contract_test_content": "orphan fixture"},
        ))
        self._assert_flush_rejected("23503")

    def test_review_report_requires_an_existing_document(self):
        self.session.add(ReviewReportModel(
            report_id=REPORT_ID,
            document_id=MISSING_ID,
            findings={"contract_test_findings": []},
            audited_at=TIMESTAMP,
        ))
        self._assert_flush_rejected("23503")

    def test_block_order_is_unique_inside_one_document(self):
        document = self._document(self._template())
        self._block(document)
        self.session.flush()
        self._block(document, block_id=SECOND_BLOCK_ID)
        self._assert_flush_rejected("23505")

    def test_same_block_order_is_allowed_in_different_documents(self):
        template = self._template()
        first = self._document(template)
        second = self._document(template, document_id=SECOND_DOCUMENT_ID, slug="persistence-test-second-document")
        self._block(first)
        self._block(second, block_id=SECOND_BLOCK_ID)
        self.session.flush()
        self.assertEqual(self.session.scalar(
            select(func.count()).select_from(CanvasBlockModel)
            .where(CanvasBlockModel.document_id.in_([DOCUMENT_ID, SECOND_DOCUMENT_ID]))
        ), 2)

    def test_metadata_contract_round_trips_through_jsonb(self):
        template = self._template()
        payload = {"contract_test": {"values": ["texto", 7, True, None], "nested": {"fixture": "á"}}}
        template.metadata_contract = payload
        self.session.flush()
        self.session.expire_all()
        self.assertEqual(self.session.get(TemplateModel, TEMPLATE_ID).metadata_contract, payload)

    def test_layout_structure_round_trips_through_jsonb(self):
        template = self._template()
        payload = {"contract_test_structure": [{"fixture": "first"}, {"fixture": "second"}]}
        template.layout_structure = payload
        self.session.flush()
        self.session.expire_all()
        self.assertEqual(self.session.get(TemplateModel, TEMPLATE_ID).layout_structure, payload)

    def test_orm_relationships_reload_and_blocks_have_contractual_order(self):
        template = self._template()
        document = self._document(template)
        self._block(document, block_id=SECOND_BLOCK_ID, order_index=1)
        self._block(document, order_index=0)
        self._review(document)
        self._review(document, report_id=SECOND_REPORT_ID, audited_at=TIMESTAMP + timedelta(hours=1))
        self.session.flush()
        self.session.expire_all()
        document = self.session.get(DocumentModel, DOCUMENT_ID)
        self.assertEqual(document.template.template_id, TEMPLATE_ID)
        self.assertIn(document, document.template.documents)
        self.assertEqual([block.order_index for block in document.canvas_blocks], [0, 1])
        self.assertTrue(all(block.document is document for block in document.canvas_blocks))
        self.assertEqual({report.report_id for report in document.review_reports}, {REPORT_ID, SECOND_REPORT_ID})
        self.assertTrue(all(report.document is document for report in document.review_reports))
        latest = self.session.scalar(
            select(ReviewReportModel)
            .where(ReviewReportModel.document_id == DOCUMENT_ID)
            .order_by(ReviewReportModel.audited_at.desc())
            .limit(1)
        )
        self.assertEqual(latest.report_id, SECOND_REPORT_ID)

    def test_timestamps_round_trip_as_timezone_aware_instants(self):
        instant = datetime(2026, 10, 25, 17, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        template = self._template()
        template.created_at = instant
        document = self._document(template)
        document.status = DocumentStatus.PUBLICADO
        document.updated_at = instant
        document.published_at = instant
        self._review(document, audited_at=instant)
        self.session.flush()
        self.session.expire_all()
        stored_document = self.session.get(DocumentModel, DOCUMENT_ID)
        values = (
            stored_document.template.created_at,
            stored_document.updated_at,
            stored_document.published_at,
            stored_document.review_reports[0].audited_at,
        )
        for value in values:
            with self.subTest(timestamp=value):
                self.assertIsNotNone(value.utcoffset())
                self.assertEqual(value, instant)

    def test_template_delete_is_restricted_while_a_document_references_it(self):
        template = self._template()
        self._document(template)
        self.session.flush()
        self.session.delete(template)
        # PostgreSQL uses 23001 for RESTRICT; missing FK references use 23503.
        self._assert_flush_rejected("23001")

    def test_deleting_a_draft_removes_its_composed_children_only(self):
        template = self._template()
        document = self._document(template)
        self._block(document)
        self._review(document)
        self.session.flush()
        self.session.delete(document)
        self.session.flush()
        self.assertEqual(self.session.scalar(
            select(func.count()).select_from(CanvasBlockModel)
            .where(CanvasBlockModel.document_id == DOCUMENT_ID)
        ), 0)
        self.assertEqual(self.session.scalar(
            select(func.count()).select_from(ReviewReportModel)
            .where(ReviewReportModel.document_id == DOCUMENT_ID)
        ), 0)
        self.assertIsNotNone(self.session.get(TemplateModel, TEMPLATE_ID))


if __name__ == "__main__":
    unittest.main()
