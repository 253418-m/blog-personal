"""Exportación aislada de POST nuevos a Quarto, sin render ni Git."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import Protocol


logger = logging.getLogger(__name__)
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class QuartoCollisionError(Exception):
    """El slug ya ocupa un directorio, incluidos artículos históricos."""


class QuartoExportError(Exception):
    """Error de filesystem que no expone rutas al cliente."""


@dataclass(frozen=True)
class QuartoExportResult:
    path: Path
    created: bool
    digest: str
    directory_id: int
    file_id: int


class QuartoExporter(Protocol):
    def export_post(self, *, slug: str, title: str, metadata_values: dict, content: str,
                    published_at: datetime) -> QuartoExportResult: ...

    def remove_export(self, result: QuartoExportResult) -> None: ...


class FileSystemQuartoExporter:
    def __init__(self, project_root: Path) -> None:
        self._project_root = Path(project_root)

    def _posts_root(self) -> Path:
        try:
            root = self._project_root.resolve(strict=True)
            posts = root / "posts"
            if posts.is_symlink() or not posts.is_dir() or posts.resolve(strict=True).parent != root:
                raise QuartoExportError("No fue posible exportar el contenido a Quarto.")
            return posts
        except OSError:
            raise QuartoExportError("No fue posible exportar el contenido a Quarto.") from None

    @staticmethod
    def _qmd(title: str, metadata_values: dict, content: str, published_at: datetime) -> str:
        # Los literales JSON son escalares/secuencias válidos en YAML y escapan
        # comillas, saltos y Unicode sin permitir cerrar el front matter.
        lines = ["---", "title: " + json.dumps(title, ensure_ascii=False),
                 "date: " + published_at.date().isoformat()]
        if "category" in metadata_values:
            lines.append("categories: " + json.dumps([metadata_values["category"]], ensure_ascii=False))
        lines.extend(["body-classes: article-page", "title-block-style: none", "toc: false", "---", "", content])
        return "\n".join(lines).rstrip("\n") + "\n"

    def export_post(self, *, slug: str, title: str, metadata_values: dict, content: str,
                    published_at: datetime) -> QuartoExportResult:
        if not SLUG_PATTERN.fullmatch(slug):
            raise QuartoExportError("No fue posible exportar el contenido a Quarto.")
        posts = self._posts_root()
        destination = posts / slug
        # El directorio se reserva atómicamente. Nunca se abre uno preexistente.
        try:
            destination.mkdir()
        except FileExistsError:
            raise QuartoCollisionError("Ya existe contenido Quarto con ese slug.") from None
        except OSError:
            raise QuartoExportError("No fue posible exportar el contenido a Quarto.") from None

        temporary: Path | None = None
        try:
            payload = self._qmd(title, metadata_values, content, published_at).encode("utf-8")
            with tempfile.NamedTemporaryFile(dir=destination, prefix=".index-", suffix=".tmp", delete=False) as file:
                temporary = Path(file.name)
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            final = destination / "index.qmd"
            os.replace(temporary, final)
            temporary = None
            if not final.is_file() or final.read_bytes() != payload:
                raise OSError("Export verification failed")
            return QuartoExportResult(final, True, hashlib.sha256(payload).hexdigest(),
                                      destination.stat().st_ino, final.stat().st_ino)
        except Exception:
            try:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
                final = destination / "index.qmd"
                if final.is_file():
                    final.unlink()
                destination.rmdir()
            except OSError:
                logger.exception("No se pudo limpiar una exportación Quarto incompleta.")
            raise QuartoExportError("No fue posible exportar el contenido a Quarto.") from None

    def remove_export(self, result: QuartoExportResult) -> None:
        if not result.created:
            return
        posts = self._posts_root()
        directory = posts / result.path.parent.name
        file = directory / "index.qmd"
        try:
            if (directory != result.path.parent or directory.is_symlink()
                    or directory.stat().st_ino != result.directory_id
                    or file.is_symlink() or file.stat().st_ino != result.file_id
                    or hashlib.sha256(file.read_bytes()).hexdigest() != result.digest
                    or {entry.name for entry in directory.iterdir()} != {"index.qmd"}):
                raise OSError("Export ownership changed")
            file.unlink()
            directory.rmdir()
        except OSError:
            logger.exception("No se pudo compensar la exportación Quarto tras fallar la transacción.")
            raise QuartoExportError("No fue posible compensar la exportación Quarto.") from None
