"""HTTP/PostgreSQL y filesystem temporal durante publicación POST."""

from contextlib import contextmanager
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.database.document_repository import SQLAlchemyDocumentRepository
from app.api.v1.endpoints.documents import get_document_service
from app.main import app
from app.services.document_service import DocumentService
from app.services.quarto_export import QuartoExportError
from tests.test_documents import DocumentHTTPTestCase


class QuartoPublishTests(DocumentHTTPTestCase):
    def test_publishing_post_exports_qmd_and_sets_db_state(self):
        document = self.seed_document(slug="nuevo-post-fixture")
        response = self.publish(document)
        self.assertEqual(response.status_code, 200)
        published = response.json()
        self.assertEqual(published["status"], "PUBLICADO")
        self.assertIsNotNone(published["published_at"])
        file = self.quarto_root / "posts/nuevo-post-fixture/index.qmd"
        self.assertTrue(file.is_file())
        qmd = file.read_text(encoding="utf-8")
        self.assertIn('title: "Post ficticio"', qmd)
        self.assertIn('categories: ["Pruebas"]', qmd)
        self.assertIn(document["content"], qmd)
        self.assertNotIn(str(self.quarto_root), response.text)

    def test_existing_historical_qmd_causes_409_without_writes(self):
        document = self.seed_document(slug="articulo-historico-ficticio")
        directory = self.quarto_root / "posts/articulo-historico-ficticio"
        directory.mkdir()
        file = directory / "index.qmd"
        file.write_text("Contenido histórico ficticio", encoding="utf-8")
        with patch.object(self.quarto_exporter, "remove_export") as compensate:
            response = self.publish(document)
        compensate.assert_not_called()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(file.read_text(encoding="utf-8"), "Contenido histórico ficticio")
        self.assertEqual(self.fetch(document).json(), document)

    def test_export_failure_leaves_draft_and_no_partial_directory(self):
        document = self.seed_document(slug="fallo-exportacion-ficticia")
        with patch("app.services.quarto_export.os.replace", side_effect=OSError("private-path-fixture")):
            response = self.publish(document)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private-path-fixture", response.text)
        self.assertEqual(self.fetch(document).json(), document)
        self.assertFalse((self.quarto_root / "posts/fallo-exportacion-ficticia").exists())

    def test_database_failure_after_export_compensates_file(self):
        document = self.seed_document(slug="fallo-db-ficticio")
        original = SQLAlchemyDocumentRepository.update

        def fail(repository, row):
            original(repository, row)
            raise SQLAlchemyError("private-db-fixture")

        with patch.object(SQLAlchemyDocumentRepository, "update", fail):
            response = self.publish(document)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.fetch(document).json(), document)
        self.assertFalse((self.quarto_root / "posts/fallo-db-ficticio").exists())

    def test_commit_failure_after_export_compensates_file(self):
        document = self.seed_document(slug="fallo-commit-ficticio")

        def failing_session_factory():
            session = self.session_factory()
            original_begin = session.begin

            @contextmanager
            def fail_at_commit():
                with original_begin():
                    yield
                    raise SQLAlchemyError("private-commit-fixture")

            session.begin = fail_at_commit
            return session

        app.dependency_overrides[get_document_service] = lambda: DocumentService(
            failing_session_factory, self.quarto_exporter
        )
        response = self.publish(document)
        app.dependency_overrides[get_document_service] = lambda: DocumentService(
            self.session_factory, self.quarto_exporter
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.fetch(document).json(), document)
        self.assertFalse((self.quarto_root / "posts/fallo-commit-ficticio").exists())

    def test_landing_publish_does_not_export_and_remains_editable(self):
        document = self.seed_landing()
        response = self.publish(document)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "PUBLICADO")
        self.assertEqual(list((self.quarto_root / "posts").iterdir()), [])
        self.assertEqual(self.put_document(document, title="Landing actualizada").status_code, 200)

    def test_published_post_stays_immutable_but_can_archive_without_touching_qmd(self):
        document = self.seed_document(slug="archivo-estable-ficticio")
        self.publish(document)
        file = self.quarto_root / "posts/archivo-estable-ficticio/index.qmd"
        content = file.read_bytes()
        self.assertEqual(self.put_document(document, title="Prohibido").status_code, 409)
        self.assertEqual(self.remove_document(document).status_code, 409)
        self.assertEqual(self.archive(document).status_code, 200)
        self.assertEqual(file.read_bytes(), content)

    def test_compensation_failure_is_reported_safely_and_keeps_export(self):
        document = self.seed_document(slug="fallo-compensacion-ficticio")
        original = SQLAlchemyDocumentRepository.update

        def fail(repository, row):
            original(repository, row)
            raise SQLAlchemyError("private-db-fixture")

        with patch.object(SQLAlchemyDocumentRepository, "update", fail), patch.object(
            self.quarto_exporter, "remove_export", side_effect=QuartoExportError("private-path-fixture")
        ):
            response = self.publish(document)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private-path-fixture", response.text)
        self.assertEqual(self.fetch(document).json(), document)
        self.assertTrue((self.quarto_root / "posts/fallo-compensacion-ficticio/index.qmd").is_file())
