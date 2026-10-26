"""Render completo de Quarto en staging y sustitución compensable de docs/."""

from dataclasses import dataclass
from html.parser import HTMLParser
import logging
from pathlib import Path
import posixpath
import shutil
import subprocess
import tempfile
from time import monotonic
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from app.services.quarto_export import SLUG_PATTERN


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
RENDER_MESSAGE = "No fue posible generar el sitio Quarto."


class QuartoRenderError(Exception):
    """Error seguro de render o de sustitución del output local."""


@dataclass(frozen=True)
class QuartoRenderResult:
    success: bool
    return_code: int
    duration_ms: int


class QuartoRenderer(Protocol):
    def render_site(self, *, staging_dir: Path, expected_slug: str,
                    expect_post: bool = True) -> QuartoRenderResult: ...


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.hrefs.extend(value for name, value in attrs if name == "href" and value is not None)


def validate_rendered_html(stage: Path, slug: str, *, expect_post: bool) -> None:
    if not (stage / "index.html").is_file():
        raise QuartoRenderError(RENDER_MESSAGE)
    post_html = stage / "posts" / slug / "index.html"
    if expect_post:
        if not post_html.is_file():
            raise QuartoRenderError(RENDER_MESSAGE)
        return
    listing = stage / "posts" / "index.html"
    if post_html.exists() or not listing.is_file():
        raise QuartoRenderError(RENDER_MESSAGE)
    try:
        links = _Links()
        links.feed(listing.read_text(encoding="utf-8"))
        target = f"/posts/{slug}"
        for href in links.hrefs:
            path = posixpath.normpath(urlsplit(urljoin("https://quarto.invalid/posts/index.html", href)).path)
            if path == target or path == f"{target}/index.html":
                raise QuartoRenderError(RENDER_MESSAGE)
    except (OSError, UnicodeError, ValueError):
        raise QuartoRenderError(RENDER_MESSAGE) from None


def validate_project(project_root: Path) -> Path:
    try:
        root = Path(project_root).resolve(strict=True)
        config = root / "_quarto.yml"
        posts = root / "posts"
        if not root.is_dir() or config.is_symlink() or not config.is_file() or posts.is_symlink() or not posts.is_dir():
            raise QuartoRenderError(RENDER_MESSAGE)
        # Exigir el output-dir explícito del proyecto; no inferir otro destino.
        in_project = False
        output_dir = None
        # Quarto acepta UTF-8 con BOM. La configuración real del proyecto usa
        # ese formato; utf-8 puro dejaba la primera clave como \ufeffproject:.
        for raw in config.read_text(encoding="utf-8-sig").splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line or not line.strip():
                continue
            if not line[0].isspace():
                in_project = line.strip() == "project:"
            elif in_project and line.startswith("  output-dir:"):
                output_dir = line.split(":", 1)[1].strip().strip("\"'")
        if output_dir != "docs" or posts.resolve(strict=True).parent != root:
            logger.error("quarto_project_validation_failed reason=output_dir_or_posts")
            raise QuartoRenderError(RENDER_MESSAGE)
        docs = root / "docs"
        if docs.is_symlink() or (docs.exists() and not docs.is_dir()):
            raise QuartoRenderError(RENDER_MESSAGE)
        return root
    except (OSError, UnicodeError):
        raise QuartoRenderError(RENDER_MESSAGE) from None


class SubprocessQuartoRenderer:
    def __init__(self, project_root: Path, executable: str = "quarto", timeout_seconds: int = 120) -> None:
        self._project_root = Path(project_root)
        self._executable = executable
        self._timeout_seconds = timeout_seconds

    def render_site(self, *, staging_dir: Path, expected_slug: str,
                    expect_post: bool = True) -> QuartoRenderResult:
        root = validate_project(self._project_root)
        if not SLUG_PATTERN.fullmatch(expected_slug) or self._timeout_seconds <= 0:
            raise QuartoRenderError(RENDER_MESSAGE)
        try:
            relative_stage = staging_dir.relative_to(root)
        except ValueError:
            raise QuartoRenderError(RENDER_MESSAGE) from None
        if len(relative_stage.parts) < 2 or relative_stage.parts[0] in {"docs", "posts"}:
            raise QuartoRenderError(RENDER_MESSAGE)
        executable = (shutil.which("quarto.exe") or shutil.which("quarto")) if self._executable == "quarto" else shutil.which(self._executable)
        if executable is None:
            logger.error("Quarto render: executable no disponible")
            raise QuartoRenderError(RENDER_MESSAGE)
        started = monotonic()
        logger.info("render_start")
        try:
            with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
                process = subprocess.run(
                    [executable, "render", str(root), "--output-dir", relative_stage.as_posix()],
                    cwd=root, stdout=stdout, stderr=stderr, timeout=self._timeout_seconds, shell=False,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            logger.error("Quarto render: timeout tras %s segundos", self._timeout_seconds)
            raise QuartoRenderError(RENDER_MESSAGE) from None
        except OSError:
            logger.error("Quarto render: fallo al ejecutar CLI")
            raise QuartoRenderError(RENDER_MESSAGE) from None
        if process.returncode != 0:
            logger.error("Quarto render: exit_code=%s", process.returncode)
            raise QuartoRenderError(RENDER_MESSAGE)
        logger.info("render_completed return_code=%s duration_ms=%s", process.returncode,
                    round((monotonic() - started) * 1000))
        try:
            validate_rendered_html(staging_dir, expected_slug, expect_post=expect_post)
        except QuartoRenderError:
            logger.error("Quarto render: falta output esperado")
            raise
        logger.info("html_validation_completed")
        return QuartoRenderResult(True, process.returncode, round((monotonic() - started) * 1000))


class QuartoRenderReceipt:
    """Backup privado vivo hasta confirmar o compensar la transacción DB."""

    def __init__(self, root: Path, workspace: tempfile.TemporaryDirectory, had_docs: bool,
                 result: QuartoRenderResult) -> None:
        self.root = root
        self.workspace = workspace
        self.had_docs = had_docs
        self.result = result

    def restore(self) -> None:
        docs = self.root / "docs"
        backup = Path(self.workspace.name) / "previous-docs"
        try:
            if docs.is_symlink() or (docs.exists() and not docs.is_dir()):
                raise OSError("docs changed unexpectedly")
            if docs.exists():
                shutil.rmtree(docs)
            if self.had_docs:
                backup.rename(docs)
            self.workspace.cleanup()
        except OSError:
            # Mantener el backup para recuperación manual si la restauración falla.
            logger.exception("No se pudo restaurar docs/ tras fallar la publicación Quarto.")
            raise QuartoRenderError("No fue posible restaurar el sitio Quarto anterior.") from None

    def finalize(self) -> None:
        try:
            self.workspace.cleanup()
        except OSError:
            logger.exception("No se pudo limpiar el backup temporal de docs/ confirmado.")


class QuartoRenderService:
    def __init__(self, project_root: Path, renderer: QuartoRenderer) -> None:
        self._project_root = Path(project_root)
        self._renderer = renderer

    def render_site(self, expected_slug: str, *, expect_post: bool = True) -> QuartoRenderReceipt:
        root = validate_project(self._project_root)
        workspace = tempfile.TemporaryDirectory(prefix=".cms-render-", dir=root)
        stage = Path(workspace.name) / "stage"
        docs = root / "docs"
        backup = Path(workspace.name) / "previous-docs"
        had_docs = docs.exists()
        moved_docs = False
        phase = "render_start"
        try:
            result = self._renderer.render_site(staging_dir=stage, expected_slug=expected_slug,
                                                expect_post=expect_post)
            phase = "render_completed"
            if not result.success:
                raise QuartoRenderError(RENDER_MESSAGE)
            validate_rendered_html(stage, expected_slug, expect_post=expect_post)
            phase = "html_validation_completed"
            if docs.is_symlink() or (docs.exists() and not docs.is_dir()):
                raise QuartoRenderError(RENDER_MESSAGE)
            # .nojekyll puede haberse colocado en el output anterior fuera de
            # Quarto; conservar solo este marcador de GitHub Pages, sin mezclar
            # HTML o assets obsoletos con el render nuevo.
            marker = docs / ".nojekyll"
            if had_docs and marker.is_file() and not marker.is_symlink() and not (stage / ".nojekyll").exists():
                shutil.copy2(marker, stage / ".nojekyll")
            if had_docs:
                docs.rename(backup)
                moved_docs = True
            logger.info("docs_backup_completed had_docs=%s", had_docs)
            phase = "docs_install_started"
            logger.info("docs_install_started")
            stage.rename(docs)
            logger.info("docs_install_completed")
            return QuartoRenderReceipt(root, workspace, had_docs, result)
        except Exception as error:
            logger.error("quarto_render_failed phase=%s error_type=%s", phase, type(error).__name__)
            if moved_docs:
                try:
                    if docs.exists():
                        shutil.rmtree(docs)
                    backup.rename(docs)
                except OSError:
                    logger.exception("No se pudo restaurar docs/ durante instalación de staging.")
                    raise QuartoRenderError("No fue posible restaurar el sitio Quarto anterior.") from None
            workspace.cleanup()
            raise QuartoRenderError(RENDER_MESSAGE) from None
