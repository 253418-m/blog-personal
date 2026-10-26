"""Renderer y sustitución de docs/ en proyectos Quarto temporales."""

from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.core.config import Settings
from app.services.quarto_render import (QuartoRenderError, QuartoRenderResult,
                                        QuartoRenderService, SubprocessQuartoRenderer)


class _FixtureRenderer:
    def __init__(self):
        self.calls = []
        self.fail = False

    def render_site(self, *, staging_dir: Path, expected_slug: str,
                    expect_post: bool = True) -> QuartoRenderResult:
        self.calls.append(expected_slug)
        staging_dir.mkdir()
        (staging_dir / "index.html").write_text("Nuevo inicio", encoding="utf-8")
        posts = staging_dir / "posts"
        posts.mkdir()
        (posts / "index.html").write_text("Catálogo nuevo", encoding="utf-8")
        if expect_post:
            target = posts / expected_slug
            target.mkdir()
            (target / "index.html").write_text("Nuevo post", encoding="utf-8")
        if self.fail:
            raise QuartoRenderError("error ficticio")
        return QuartoRenderResult(True, 0, 12)


class QuartoRenderTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "posts").mkdir()
        (self.root / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: docs\nformat: html\n", encoding="utf-8"
        )
        self.renderer = _FixtureRenderer()
        self.service = QuartoRenderService(self.root, self.renderer)

    def test_staging_replaces_entire_docs_and_finalizes_backup(self):
        docs = self.root / "docs"
        docs.mkdir()
        (docs / "obsolete.html").write_text("Anterior", encoding="utf-8")
        (docs / ".nojekyll").write_bytes(b"")
        receipt = self.service.render_site("nuevo-post")
        self.assertEqual(self.renderer.calls, ["nuevo-post"])
        self.assertFalse((docs / "obsolete.html").exists())
        self.assertTrue((docs / ".nojekyll").is_file())
        self.assertEqual((docs / "posts/nuevo-post/index.html").read_text(encoding="utf-8"), "Nuevo post")
        workspace = Path(receipt.workspace.name)
        self.assertTrue((workspace / "previous-docs/obsolete.html").exists())
        receipt.finalize()
        self.assertFalse(workspace.exists())

    def test_real_utf8_bom_project_config_installs_staging_over_populated_docs(self):
        # La configuración real comienza con EF BB BF: antes de la corrección
        # validate_project no reconocía project: y devolvía 500 antes de render.
        actual_config = Path(__file__).resolve().parents[2] / "_quarto.yml"
        config_bytes = actual_config.read_bytes()
        self.assertTrue(config_bytes.startswith(b"\xef\xbb\xbf"))
        (self.root / "_quarto.yml").write_bytes(config_bytes)
        docs = self.root / "docs"
        docs.mkdir()
        for number in range(75):
            (docs / f"previous-{number}.html").write_text("Anterior", encoding="utf-8")
        with self.assertLogs("app.services.quarto_render", level="INFO") as captured:
            receipt = self.service.render_site("nuevo-post")
        self.assertEqual(self.renderer.calls, ["nuevo-post"])
        self.assertTrue((docs / "index.html").is_file())
        self.assertTrue((docs / "posts/nuevo-post/index.html").is_file())
        self.assertFalse((docs / "previous-0.html").exists())
        for phase in ("docs_backup_completed", "docs_install_started", "docs_install_completed"):
            self.assertTrue(any(phase in line for line in captured.output))
        receipt.finalize()

    def test_restore_existing_docs_exactly_after_failure(self):
        docs = self.root / "docs"
        docs.mkdir()
        (docs / "old.html").write_bytes(b"original")
        receipt = self.service.render_site("nuevo-post")
        receipt.restore()
        self.assertEqual({p.relative_to(docs).as_posix(): p.read_bytes() for p in docs.rglob('*') if p.is_file()},
                         {"old.html": b"original"})
        self.assertFalse(Path(receipt.workspace.name).exists())

    def test_restore_to_absent_docs_when_none_existed(self):
        receipt = self.service.render_site("nuevo-post")
        self.assertTrue((self.root / "docs/posts/nuevo-post/index.html").is_file())
        receipt.restore()
        self.assertFalse((self.root / "docs").exists())

    def test_render_error_keeps_docs_and_cleans_workspace(self):
        docs = self.root / "docs"
        docs.mkdir()
        (docs / "original.html").write_bytes(b"original")
        self.renderer.fail = True
        with self.assertRaises(QuartoRenderError):
            self.service.render_site("nuevo-post")
        self.assertEqual((docs / "original.html").read_bytes(), b"original")
        self.assertEqual(list(self.root.glob('.cms-render-*')), [])

    def test_archive_rejects_stale_post_html_or_listing_link(self):
        docs = self.root / "docs"
        docs.mkdir()
        (docs / "original.html").write_bytes(b"original")

        def stale_render(*, staging_dir, expected_slug, expect_post):
            staging_dir.mkdir()
            (staging_dir / "index.html").write_text("Home", encoding="utf-8")
            posts = staging_dir / "posts"
            posts.mkdir()
            (posts / "index.html").write_text(
                '<a href="nuevo-post/">Still listed</a>' if not stale_html else "No link",
                encoding="utf-8",
            )
            if stale_html:
                target = posts / expected_slug
                target.mkdir()
                (target / "index.html").write_text("Stale", encoding="utf-8")
            return QuartoRenderResult(True, 0, 1)

        for stale_html in (True, False):
            with self.subTest(stale_html=stale_html), patch.object(self.renderer, "render_site", stale_render):
                with self.assertRaises(QuartoRenderError):
                    self.service.render_site("nuevo-post", expect_post=False)
                self.assertEqual((docs / "original.html").read_bytes(), b"original")
                self.assertEqual(list(self.root.glob('.cms-render-*')), [])

    def test_stage_install_failure_restores_original_docs(self):
        docs = self.root / "docs"
        docs.mkdir()
        (docs / "original.html").write_bytes(b"original")
        original = Path.rename

        def fail_stage(path, target):
            if path.name == "stage":
                raise OSError("fixture-install-failure")
            return original(path, target)

        with patch.object(Path, "rename", fail_stage), self.assertRaises(QuartoRenderError):
            self.service.render_site("nuevo-post")
        self.assertEqual((docs / "original.html").read_bytes(), b"original")
        self.assertEqual(list(self.root.glob('.cms-render-*')), [])

    def test_wrong_project_or_output_dir_fails_before_render(self):
        for config in (None, "project:\n  type: website\n  output-dir: elsewhere\n"):
            if config is None:
                (self.root / "_quarto.yml").unlink(missing_ok=True)
            else:
                (self.root / "_quarto.yml").write_text(config, encoding="utf-8")
            with self.assertRaises(QuartoRenderError):
                self.service.render_site("nuevo-post")
        self.assertEqual(self.renderer.calls, [])

    def test_missing_posts_fails_before_render(self):
        (self.root / "posts").rmdir()
        with self.assertRaises(QuartoRenderError):
            self.service.render_site("nuevo-post")
        self.assertEqual(self.renderer.calls, [])

    def test_subprocess_uses_list_cwd_timeout_and_no_shell(self):
        renderer = SubprocessQuartoRenderer(self.root, "quarto", 23)
        with TemporaryDirectory(dir=self.root, prefix=".cms-render-") as temporary:
            stage = Path(temporary) / "stage"

            def complete(argv, **kwargs):
                stage.mkdir()
                (stage / "index.html").write_text("Home", encoding="utf-8")
                target = stage / "posts/nuevo-post"
                target.mkdir(parents=True)
                (target / "index.html").write_text("Post", encoding="utf-8")
                self.assertEqual(argv[1:3], ["render", str(self.root)])
                self.assertEqual(argv[3], "--output-dir")
                self.assertEqual(kwargs["cwd"], self.root)
                self.assertEqual(kwargs["timeout"], 23)
                self.assertIs(kwargs["shell"], False)
                return subprocess.CompletedProcess(argv, 0)

            with patch("app.services.quarto_render.shutil.which", return_value="quarto.exe"), patch(
                "app.services.quarto_render.subprocess.run", side_effect=complete
            ):
                result = renderer.render_site(staging_dir=stage, expected_slug="nuevo-post")
            self.assertTrue(result.success)
            self.assertEqual(result.return_code, 0)

    def test_subprocess_errors_are_safe(self):
        renderer = SubprocessQuartoRenderer(self.root, "quarto", 1)
        with TemporaryDirectory(dir=self.root, prefix=".cms-render-") as temporary:
            stage = Path(temporary) / "stage"
            for side_effect in (subprocess.CompletedProcess([], 2),
                                subprocess.TimeoutExpired(["fixture"], 1), FileNotFoundError("private-fixture")):
                options = ({"return_value": side_effect} if isinstance(side_effect, subprocess.CompletedProcess)
                           else {"side_effect": side_effect})
                with self.subTest(effect=type(side_effect)), patch(
                    "app.services.quarto_render.shutil.which", return_value="quarto.exe"
                ), patch("app.services.quarto_render.subprocess.run", **options):
                    with self.assertRaises(QuartoRenderError) as raised:
                        renderer.render_site(staging_dir=stage, expected_slug="nuevo-post")
                    self.assertEqual(str(raised.exception), "No fue posible generar el sitio Quarto.")

    def test_missing_executable_and_output_are_errors(self):
        renderer = SubprocessQuartoRenderer(self.root)
        with TemporaryDirectory(dir=self.root, prefix=".cms-render-") as temporary:
            stage = Path(temporary) / "stage"
            with patch("app.services.quarto_render.shutil.which", return_value=None), self.assertRaises(QuartoRenderError):
                renderer.render_site(staging_dir=stage, expected_slug="nuevo-post")
            with patch("app.services.quarto_render.shutil.which", return_value="quarto.exe"), patch(
                "app.services.quarto_render.subprocess.run", return_value=subprocess.CompletedProcess([], 0)
            ), self.assertRaises(QuartoRenderError):
                renderer.render_site(staging_dir=stage, expected_slug="nuevo-post")

    def test_real_quarto_renders_only_temporary_site(self):
        (self.root / "index.qmd").write_text("---\ntitle: Home\n---\n\n# Home\n", encoding="utf-8")
        post = self.root / "posts/nuevo-post"
        post.mkdir()
        (post / "index.qmd").write_text("---\ntitle: Fixture\n---\n\n# Fixture\n", encoding="utf-8")
        service = QuartoRenderService(self.root, SubprocessQuartoRenderer(self.root, timeout_seconds=120))
        receipt = service.render_site("nuevo-post")
        self.assertTrue(receipt.result.success)
        self.assertTrue((self.root / "docs/posts/nuevo-post/index.html").is_file())
        receipt.finalize()

    def test_renderer_settings_accept_environment_override_and_positive_timeout(self):
        fixture = dict(database_url="postgresql+psycopg://fixture@localhost:5432/cms_core",
                       jwt_secret_key="fixture-secret-with-more-than-thirty-two-bytes")
        with patch.dict(os.environ, {"QUARTO_PROJECT_ROOT": str(self.root),
                                  "QUARTO_EXECUTABLE": "quarto.exe", "QUARTO_RENDER_TIMEOUT_SECONDS": "37"}):
            settings = Settings(_env_file=None, **fixture)
        self.assertEqual(settings.quarto_project_root, self.root)
        self.assertEqual(settings.quarto_executable, "quarto.exe")
        self.assertEqual(settings.quarto_render_timeout_seconds, 37)
