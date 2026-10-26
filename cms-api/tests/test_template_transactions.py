"""Confirmación transaccional y exclusión entre conexiones, sin datos persistentes."""

import unittest
from unittest.mock import MagicMock, Mock, patch

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.infrastructure.database.template_repository import SQLAlchemyTemplateRepository
from app.repositories.interfaces import TemplateRepository
from app.schemas.template import TemplateCreateRequest
from app.services.template_service import TemplateService, TemplateStorageUnavailable
from tests.postgresql import PostgreSQLTestCase


class TemplateCommitTests(unittest.TestCase):
    def test_commit_failure_does_not_return_created_template(self):
        session = MagicMock(spec=Session)
        session.__enter__.return_value = session
        session.begin.return_value.__exit__.side_effect = SQLAlchemyError("private-commit-fixture")
        repository = Mock(spec=TemplateRepository)
        repository.get_by_name.return_value = None
        repository.get_default.return_value = None
        repository.count.return_value = 0
        request = TemplateCreateRequest(
            name="Commit fixture", target_type="POST", is_default=True, allow_published_edit=False,
            metadata_contract=[{"field_key": "title", "expected_type": "STRING", "is_required": True}],
            layout_structure={},
        )
        with patch("app.services.template_service.SQLAlchemyTemplateRepository", return_value=repository):
            with self.assertRaises(TemplateStorageUnavailable) as raised:
                TemplateService(lambda: session).create_template(request)
        self.assertNotIn("private-commit-fixture", str(raised.exception))


class TemplateLockTests(PostgreSQLTestCase):
    def test_catalog_write_lock_excludes_competing_connection_without_writing_rows(self):
        SQLAlchemyTemplateRepository(self.session).lock_catalog()
        with self.engine.connect() as competitor:
            with self.assertRaises(OperationalError) as raised:
                with competitor.begin():
                    competitor.execute(text("LOCK TABLE public.templates IN SHARE ROW EXCLUSIVE MODE NOWAIT"))
        self.assertEqual(raised.exception.orig.sqlstate, "55P03")
