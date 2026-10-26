"""Exporter aislado: todos los archivos se crean en un Quarto temporal."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.services.quarto_export import (FileSystemQuartoExporter, QuartoCollisionError,
                                        QuartoExportError)


class QuartoExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.posts = self.root / "posts"
        self.posts.mkdir()
        self.exporter = FileSystemQuartoExporter(self.root)
        self.fields = dict(slug="cms-prueba", title='Título: "área"',
                           metadata_values={"category": 'Redes: "avanzadas"', "reading_time": 8},
                           content="# Introducción\n\nContenido ficticio.\n",
                           published_at=datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc))

    def test_creates_directory_qmd_and_existing_front_matter_conventions(self):
        result = self.exporter.export_post(**self.fields)
        self.assertTrue(result.created)
        self.assertEqual(result.path, self.posts / "cms-prueba/index.qmd")
        qmd = result.path.read_text(encoding="utf-8")
        self.assertEqual(qmd, '---\ntitle: "Título: \\"área\\""\ndate: 2026-10-26\n'
                         'categories: ["Redes: \\"avanzadas\\""]\nbody-classes: article-page\n'
                         'title-block-style: none\ntoc: false\n---\n\n'
                         '# Introducción\n\nContenido ficticio.\n')
        self.assertNotIn("reading_time", qmd)

    def test_title_and_category_cannot_inject_front_matter(self):
        fields = {**self.fields, "title": 'A\n---\ndraft: true',
                  "metadata_values": {"category": 'X\n---\nexecute: true'}}
        qmd = self.exporter.export_post(**fields).path.read_text(encoding="utf-8")
        self.assertEqual(qmd.splitlines().count("---"), 2)
        self.assertIn('A\\n---\\ndraft: true', qmd)
        self.assertIn('X\\n---\\nexecute: true', qmd)

    def test_existing_directory_is_untouched(self):
        existing = self.posts / "cms-prueba"
        existing.mkdir()
        file = existing / "index.qmd"
        file.write_text("Artículo histórico", encoding="utf-8")
        with self.assertRaises(QuartoCollisionError):
            self.exporter.export_post(**self.fields)
        self.assertEqual(file.read_text(encoding="utf-8"), "Artículo histórico")

    def test_rejects_traversal(self):
        for slug in ("../outside", "a/b", "..", "A", "a\\b"):
            with self.subTest(slug=slug), self.assertRaises(QuartoExportError):
                self.exporter.export_post(**{**self.fields, "slug": slug})
        self.assertEqual(list(self.posts.iterdir()), [])

    def test_rejects_symlinked_posts_when_supported(self):
        alternative = self.root / "alternative"
        alternative.mkdir()
        try:
            probe = self.root / "posts-link-probe"
            probe.symlink_to(alternative, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.assertEqual(list(self.posts.iterdir()), [])
            return
        probe.unlink()
        self.posts.rmdir()
        self.posts.symlink_to(alternative, target_is_directory=True)
        with self.assertRaises(QuartoExportError):
            self.exporter.export_post(**self.fields)
        self.assertEqual(list(alternative.iterdir()), [])

    def test_failed_write_removes_temporary_file_and_directory(self):
        with patch("app.services.quarto_export.os.replace", side_effect=OSError("fixture")):
            with self.assertRaises(QuartoExportError):
                self.exporter.export_post(**self.fields)
        self.assertEqual(list(self.posts.iterdir()), [])

    def test_compensation_removes_only_its_unchanged_export(self):
        result = self.exporter.export_post(**self.fields)
        self.exporter.remove_export(result)
        self.assertEqual(list(self.posts.iterdir()), [])

    def test_compensation_refuses_to_remove_modified_export(self):
        result = self.exporter.export_post(**self.fields)
        result.path.write_text("Revisado externamente", encoding="utf-8")
        with self.assertRaises(QuartoExportError):
            self.exporter.remove_export(result)
        self.assertEqual(result.path.read_text(encoding="utf-8"), "Revisado externamente")

    def test_absent_category_is_omitted(self):
        qmd = self.exporter.export_post(**{**self.fields, "metadata_values": {}}).path.read_text(encoding="utf-8")
        self.assertNotIn("categories:", qmd)
