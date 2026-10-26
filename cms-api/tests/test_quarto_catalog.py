"""El catálogo Quarto descubre posts desde QMD sin tocar el sitio real."""

from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _render(root: Path) -> str:
    result = subprocess.run(
        ["quarto", "render"], cwd=root, capture_output=True, text=True, timeout=180
    )
    if result.returncode:
        raise AssertionError(result.stderr[-2000:] or result.stdout[-2000:])
    return (root / "docs/posts/index.html").read_text(encoding="utf-8")


def _write_post(root: Path, slug: str, front_matter: str) -> None:
    post = root / "posts" / slug / "index.qmd"
    post.parent.mkdir(parents=True)
    post.write_text(f"---\n{front_matter}---\n\nContenido del artículo.\n", encoding="utf-8")


class QuartoCatalogTests(unittest.TestCase):
    def test_new_cms_post_appears_without_editing_catalog_source(self):
        self.assertIsNotNone(shutil.which("quarto"))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("_quarto.yml", "styles.css", ".nojekyll", "posts/index.qmd", "posts/_metadata.yml"):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(PROJECT_ROOT / relative, target)
            (root / "index.qmd").write_text("---\ntitle: Inicio\n---\n", encoding="utf-8")
            (root / "about.qmd").write_text("---\ntitle: Sobre mí\n---\n", encoding="utf-8")
            project = root / "proyectos/puravida/index.qmd"
            project.parent.mkdir(parents=True)
            project.write_text("---\ntitle: PuraVida\n---\n", encoding="utf-8")
            _write_post(root, "antiguo", "title: Antiguo\ndate: 2025-01-01\ndescription: Resumen\n")
            _write_post(root, "reciente", "title: Reciente\ndate: 2026-01-01\ncategories: [Redes]\n")
            _write_post(root, "plantilla", "title: Plantilla\ndraft: true\n")
            private = root / "cms-api/api-docs/implementation-plan.md"
            private.parent.mkdir(parents=True)
            private.write_text("---\ntitle: Interno\n---\nMARCADOR_INTERNO", encoding="utf-8")

            catalog_source = (root / "posts/index.qmd").read_bytes()
            before = _render(root)
            self.assertLess(before.index("reciente/index.html"), before.index("antiguo/index.html"))
            self.assertNotIn("plantilla/index.html", before)
            self.assertNotIn("nuevo-cms/index.html", before)

            # Misma metadata que emite el exporter CMS: sin description ni image.
            _write_post(root, "nuevo-cms", "title: Nuevo CMS\ndate: 2026-10-26\n"
                        "categories: [Pruebas]\nbody-classes: article-page\n"
                        "title-block-style: none\ntoc: false\n")
            after = _render(root)
            self.assertEqual((root / "posts/index.qmd").read_bytes(), catalog_source)
            self.assertLess(after.index("nuevo-cms/index.html"), after.index("reciente/index.html"))
            self.assertIn("Pruebas", after)
            self.assertNotIn("plantilla/index.html", after)
            self.assertTrue((root / "docs/posts/nuevo-cms/index.html").is_file())
            for relative in ("index.html", "about.html", "proyectos/puravida/index.html"):
                self.assertTrue((root / "docs" / relative).is_file(), relative)
            self.assertFalse((root / "docs/cms-api").exists())
            search = (root / "docs/search.json").read_text(encoding="utf-8")
            self.assertNotIn("cms-api", search)
            self.assertNotIn("MARCADOR_INTERNO", search)

    def test_real_posts_and_project_render_in_temporary_copy(self):
        self.assertIsNotNone(shutil.which("quarto"))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("_quarto.yml", "index.qmd", "about.qmd", "styles.css", ".nojekyll"):
                shutil.copy2(PROJECT_ROOT / relative, root / relative)
            for name in ("posts", "proyectos", "images"):
                shutil.copytree(PROJECT_ROOT / name, root / name)
            private = root / "cms-api/api-docs/implementation-plan.md"
            private.parent.mkdir(parents=True)
            shutil.copy2(PROJECT_ROOT / "cms-api/api-docs/implementation-plan.md", private)

            catalog = _render(root)
            sources = sorted((root / "posts").glob("*/index.qmd"))
            self.assertEqual(len(sources), 13)
            included = [source for source in sources if source.parent.name != "plantilla"]
            self.assertEqual(len(included), 12)
            for source in included:
                slug = source.parent.name
                self.assertIn(f"{slug}/index.html", catalog)
                self.assertTrue((root / "docs/posts" / slug / "index.html").is_file())
            self.assertNotIn("plantilla/index.html", catalog)
            for slug in ("introduccion-redes", "inteligencia-artificial", "aplicacion-web-moderna",
                         "cms-prueba-render"):
                self.assertIn(f"{slug}/index.html", catalog)
            self.assertLess(catalog.index("cms-prueba-render/index.html"),
                            catalog.index("aplicacion-web-moderna/index.html"))
            for relative in ("index.html", "about.html", "proyectos/puravida/index.html"):
                self.assertTrue((root / "docs" / relative).is_file(), relative)
            self.assertIn("PuraVida", catalog)
            self.assertFalse((root / "docs/cms-api").exists())
            search = (root / "docs/search.json").read_text(encoding="utf-8")
            self.assertNotIn("cms-api", search)
            self.assertNotIn("implementation-plan", search)


if __name__ == "__main__":
    unittest.main()
