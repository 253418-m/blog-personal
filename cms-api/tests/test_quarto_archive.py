"""Retirada y compensación de POST sobre PostgreSQL y Quarto temporales."""

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.endpoints.documents import get_document_service
from app.main import app
from app.services.document_service import DocumentService
from app.services.quarto_export import FileSystemQuartoExporter, QuartoExportError
from app.services.quarto_render import QuartoRenderError, QuartoRenderService, SubprocessQuartoRenderer
from tests.test_documents import DocumentHTTPTestCase


class QuartoWithdrawalTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "posts").mkdir()
        self.exporter = FileSystemQuartoExporter(self.root)

    def test_withdraw_restores_exact_bytes_and_cleans_only_empty_directory(self):
        folder = self.root / "posts/fixture-post"
        folder.mkdir()
        source = folder / "index.qmd"
        payload = b"\xef\xbb\xbf---\r\ntitle: \"Prueba\"\r\n---\r\n"
        source.write_bytes(payload)
        receipt = self.exporter.withdraw_post("fixture-post")
        self.assertTrue(receipt.existed)
        self.assertEqual(receipt.original_bytes, payload)
        self.assertTrue(receipt.removed_directory)
        self.assertFalse(folder.exists())
        self.exporter.restore_withdrawal(receipt)
        self.assertEqual(source.read_bytes(), payload)

    def test_extra_files_survive_withdraw_and_restore(self):
        folder = self.root / "posts/fixture-post"
        folder.mkdir()
        (folder / "index.qmd").write_bytes(b"qmd")
        (folder / "image.png").write_bytes(b"image")
        receipt = self.exporter.withdraw_post("fixture-post")
        self.assertFalse(receipt.removed_directory)
        self.assertEqual((folder / "image.png").read_bytes(), b"image")
        self.exporter.restore_withdrawal(receipt)
        self.assertEqual((folder / "index.qmd").read_bytes(), b"qmd")
        self.assertEqual((folder / "image.png").read_bytes(), b"image")

    def test_missing_qmd_is_not_created_by_rollback(self):
        receipt = self.exporter.withdraw_post("missing-post")
        self.assertFalse(receipt.existed)
        self.exporter.restore_withdrawal(receipt)
        self.assertFalse((self.root / "posts/missing-post").exists())

    def test_restore_does_not_overwrite_a_new_source(self):
        folder = self.root / "posts/fixture-post"
        folder.mkdir()
        source = folder / "index.qmd"
        source.write_bytes(b"original")
        receipt = self.exporter.withdraw_post("fixture-post")
        folder.mkdir()
        source.write_bytes(b"new content")
        with self.assertRaises(QuartoExportError):
            self.exporter.restore_withdrawal(receipt)
        self.assertEqual(source.read_bytes(), b"new content")

    def test_traversal_and_symlink_are_rejected(self):
        with self.assertRaises(QuartoExportError):
            self.exporter.withdraw_post("../outside")
        folder = self.root / "posts/fixture-post"
        folder.mkdir()
        (folder / "index.qmd").write_bytes(b"unchanged")
        original_is_symlink = Path.is_symlink

        def pretend_symlink(path):
            return path == folder / "index.qmd" or original_is_symlink(path)

        with patch.object(Path, "is_symlink", pretend_symlink), self.assertRaises(QuartoExportError):
            self.exporter.withdraw_post("fixture-post")
        self.assertEqual((folder / "index.qmd").read_bytes(), b"unchanged")


class QuartoArchiveTests(DocumentHTTPTestCase):
    def test_archive_removes_qmd_html_listing_and_preserves_history(self):
        historic = self.quarto_root / "posts/historic"
        historic.mkdir()
        (historic / "index.qmd").write_bytes(b"historic")
        document = self.seed_document(slug="archive-fixture")
        published = self.publish(document).json()
        qmd = self.quarto_root / "posts/archive-fixture/index.qmd"
        self.assertTrue(qmd.is_file())
        response = self.archive(document)
        self.assertEqual(response.status_code, 200, response.text)
        archived = response.json()
        self.assertEqual(archived["status"], "ARCHIVADO")
        self.assertEqual(archived["published_at"], published["published_at"])
        self.assertNotEqual(archived["updated_at"], published["updated_at"])
        self.assertFalse(qmd.exists())
        self.assertFalse((self.quarto_root / "docs/posts/archive-fixture/index.html").exists())
        self.assertTrue((self.quarto_root / "docs/index.html").is_file())
        self.assertTrue((self.quarto_root / "docs/posts/index.html").is_file())
        self.assertEqual((historic / "index.qmd").read_bytes(), b"historic")

    def test_render_failure_restores_qmd_docs_and_published_state(self):
        document = self.seed_document(slug="archive-render-failure")
        published = self.publish(document).json()
        qmd = self.quarto_root / "posts/archive-render-failure/index.qmd"
        original = qmd.read_bytes()
        html = self.quarto_root / "docs/posts/archive-render-failure/index.html"
        old_html = html.read_bytes()
        with patch.object(self.quarto_render_service, "render_site",
                          side_effect=QuartoRenderError("private-fixture")):
            response = self.archive(document)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "No fue posible actualizar el sitio Quarto.")
        self.assertEqual(self.fetch(document).json(), published)
        self.assertEqual(qmd.read_bytes(), original)
        self.assertEqual(html.read_bytes(), old_html)

    def test_stage_install_failure_restores_qmd_docs_and_published_state(self):
        document = self.seed_document(slug="archive-install-failure")
        published = self.publish(document).json()
        qmd = self.quarto_root / "posts/archive-install-failure/index.qmd"
        original = qmd.read_bytes()
        docs = self.quarto_root / "docs"
        (docs / "previous-extra.html").write_bytes(b"previous")
        rename = Path.rename

        def fail_stage(path, target):
            if path.name == "stage":
                raise OSError("private-install-fixture")
            return rename(path, target)

        with patch.object(Path, "rename", fail_stage):
            response = self.archive(document)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.fetch(document).json(), published)
        self.assertEqual(qmd.read_bytes(), original)
        self.assertEqual((docs / "previous-extra.html").read_bytes(), b"previous")
        self.assertTrue((docs / "posts/archive-install-failure/index.html").is_file())

    def test_commit_failure_restores_qmd_and_docs(self):
        document = self.seed_document(slug="archive-commit-failure")
        published = self.publish(document).json()
        qmd = self.quarto_root / "posts/archive-commit-failure/index.qmd"
        original = qmd.read_bytes()
        docs = self.quarto_root / "docs"
        (docs / "prior-extra.html").write_bytes(b"prior")

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
            failing_session_factory, self.quarto_exporter, self.quarto_render_service
        )
        try:
            response = self.archive(document)
        finally:
            app.dependency_overrides[get_document_service] = lambda: DocumentService(
                self.session_factory, self.quarto_exporter, self.quarto_render_service
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.fetch(document).json(), published)
        self.assertEqual(qmd.read_bytes(), original)
        self.assertTrue((docs / "posts/archive-commit-failure/index.html").is_file())
        self.assertEqual((docs / "prior-extra.html").read_bytes(), b"prior")

    def test_missing_qmd_still_archives_after_render(self):
        document = self.seed_document(slug="archive-missing-source")
        self.publish(document)
        qmd = self.quarto_root / "posts/archive-missing-source/index.qmd"
        qmd.unlink()
        response = self.archive(document)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ARCHIVADO")
        self.assertFalse(qmd.exists())
        self.assertFalse((self.quarto_root / "docs/posts/archive-missing-source/index.html").exists())

    def test_missing_qmd_render_failure_does_not_invent_source(self):
        document = self.seed_document(slug="missing-source-failure")
        published = self.publish(document).json()
        qmd = self.quarto_root / "posts/missing-source-failure/index.qmd"
        qmd.unlink()
        with patch.object(self.quarto_render_service, "render_site",
                          side_effect=QuartoRenderError("private-fixture")):
            self.assertEqual(self.archive(document).status_code, 500)
        self.assertEqual(self.fetch(document).json(), published)
        self.assertFalse(qmd.exists())
        self.assertTrue((self.quarto_root / "docs/posts/missing-source-failure/index.html").is_file())

    def test_archive_preserves_extra_post_files(self):
        document = self.seed_document(slug="extra-files-fixture")
        self.publish(document)
        folder = self.quarto_root / "posts/extra-files-fixture"
        (folder / "image.png").write_bytes(b"image")
        self.assertEqual(self.archive(document).status_code, 200)
        self.assertFalse((folder / "index.qmd").exists())
        self.assertEqual((folder / "image.png").read_bytes(), b"image")

    def test_landing_archive_does_not_withdraw_or_render(self):
        document = self.seed_landing()
        self.publish(document)
        with patch.object(self.quarto_exporter, "withdraw_post") as withdraw, patch.object(
            self.quarto_render_service, "render_site"
        ) as render:
            self.assertEqual(self.archive(document).status_code, 200)
        withdraw.assert_not_called()
        render.assert_not_called()


class RealQuartoArchiveTests(unittest.TestCase):
    def test_temporary_project_withdrawal_removes_html_and_listing_entry(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_quarto.yml").write_text(
                "project:\n  type: website\n  output-dir: docs\n  render:\n"
                "    - index.qmd\n    - posts/**/*.qmd\nformat: html\n", encoding="utf-8"
            )
            (root / "index.qmd").write_text("---\ntitle: Home\n---\n# Home\n", encoding="utf-8")
            posts = root / "posts"
            posts.mkdir()
            (posts / "index.qmd").write_text(
                '---\ntitle: Catalog\nlisting:\n  contents: "*/index.qmd"\n'
                '  type: default\n  sort: "date desc"\n---\n', encoding="utf-8"
            )
            for slug, title in (("to-withdraw", "Withdraw fixture"), ("keep-post", "Keep fixture")):
                folder = posts / slug
                folder.mkdir()
                (folder / "index.qmd").write_text(
                    f'---\ntitle: "{title}"\ndate: 2026-10-26\n---\n# {title}\n', encoding="utf-8"
                )
            service = QuartoRenderService(root, SubprocessQuartoRenderer(root))
            first = service.render_site("to-withdraw")
            first.finalize()
            self.assertTrue((root / "docs/posts/to-withdraw/index.html").is_file())
            self.assertIn("to-withdraw", (root / "docs/posts/index.html").read_text(encoding="utf-8"))
            receipt = FileSystemQuartoExporter(root).withdraw_post("to-withdraw")
            second = service.render_site("to-withdraw", expect_post=False)
            second.finalize()
            self.assertFalse((root / "docs/posts/to-withdraw/index.html").exists())
            self.assertTrue((root / "docs/index.html").is_file())
            self.assertTrue((root / "docs/posts/index.html").is_file())
            self.assertTrue((root / "docs/posts/keep-post/index.html").is_file())
            listing = (root / "docs/posts/index.html").read_text(encoding="utf-8")
            self.assertNotIn("to-withdraw", listing)
            self.assertIn("keep-post", listing)
            self.assertTrue(receipt.existed)
