"""La configuración real de Quarto publica solo contenido del sitio."""

from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class QuartoIsolationTests(unittest.TestCase):
    def test_real_config_excludes_backend_and_staging_from_temporary_site(self):
        if shutil.which("quarto") is None:
            self.fail("Quarto debe estar disponible para comprobar el aislamiento")

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "_quarto.yml").write_bytes((PROJECT_ROOT / "_quarto.yml").read_bytes())
            pages = (
                "index.qmd",
                "about.qmd",
                "posts/index.qmd",
                "posts/publico/index.qmd",
                "proyectos/puravida/index.qmd",
            )
            for relative in pages:
                page = root / relative
                page.parent.mkdir(parents=True, exist_ok=True)
                page.write_text("---\ntitle: Página pública\n---\n\nContenido público.\n", encoding="utf-8")

            (root / "styles.css").write_text("body { color: black; }\n", encoding="utf-8")
            (root / ".nojekyll").write_bytes(b"")
            image = root / "images/publico.txt"
            image.parent.mkdir()
            image.write_text("recurso público", encoding="utf-8")
            private = root / "cms-api/api-docs/implementation-plan.md"
            private.parent.mkdir(parents=True)
            private.write_text("---\ntitle: Interno\n---\n\nMARCADOR_INTERNO\n", encoding="utf-8")
            (root / "cms-api/private.py").write_text("MARCADOR_INTERNO", encoding="utf-8")
            (root / "README.md").write_text("MARCADOR_INTERNO", encoding="utf-8")
            for name in (".cms-render-dinamico", ".quarto-staging-dinamico"):
                staging = root / name / "stage"
                staging.mkdir(parents=True)
                (staging / "secret.md").write_text("MARCADOR_INTERNO", encoding="utf-8")
            stale = root / "docs/cms-api/api-docs/implementation-plan.html"
            stale.parent.mkdir(parents=True)
            stale.write_text("salida anterior", encoding="utf-8")

            result = subprocess.run(
                ["quarto", "render"], cwd=root, capture_output=True, text=True, timeout=120
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            output = root / "docs"
            for relative in (
                "index.html",
                "about.html",
                "posts/index.html",
                "posts/publico/index.html",
                "proyectos/puravida/index.html",
                "styles.css",
                "images/publico.txt",
                ".nojekyll",
            ):
                self.assertTrue((output / relative).is_file(), relative)
            for relative in ("cms-api", ".cms-render-dinamico", ".quarto-staging-dinamico"):
                self.assertFalse((output / relative).exists(), relative)
            search = (output / "search.json").read_text(encoding="utf-8")
            for forbidden in ("cms-api", "implementation-plan", "MARCADOR_INTERNO"):
                self.assertNotIn(forbidden, search)
            self.assertNotIn("cms-api", (output / "index.html").read_text(encoding="utf-8"))
            sitemap = output / "sitemap.xml"
            if sitemap.exists():
                self.assertNotIn("cms-api", sitemap.read_text(encoding="utf-8"))

    def test_real_public_pages_render_in_a_temporary_copy(self):
        if shutil.which("quarto") is None:
            self.fail("Quarto debe estar disponible para comprobar el sitio público")

        with TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("_quarto.yml", "index.qmd", "about.qmd", "styles.css", ".nojekyll"):
                shutil.copy2(PROJECT_ROOT / relative, root / relative)
            for name in ("posts", "proyectos", "images"):
                shutil.copytree(PROJECT_ROOT / name, root / name)
            private = root / "cms-api/api-docs/implementation-plan.md"
            private.parent.mkdir(parents=True)
            shutil.copy2(PROJECT_ROOT / "cms-api/api-docs/implementation-plan.md", private)

            result = subprocess.run(
                ["quarto", "render"], cwd=root, capture_output=True, text=True, timeout=180
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            output = root / "docs"
            for source in (root / "index.qmd", root / "about.qmd", *(root / "posts").rglob("*.qmd"),
                           *(root / "proyectos").rglob("*.qmd")):
                html = output / source.relative_to(root).with_suffix(".html")
                self.assertTrue(html.is_file(), str(html.relative_to(output)))
            self.assertFalse((output / "cms-api").exists())
            search = (output / "search.json").read_text(encoding="utf-8")
            self.assertNotIn("cms-api", search)
            self.assertNotIn("implementation-plan", search)
            sitemap = output / "sitemap.xml"
            if sitemap.exists():
                self.assertNotIn("cms-api", sitemap.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
