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


@dataclass(frozen=True)
class QuartoWithdrawalReceipt:
    slug: str
    existed: bool
    original_bytes: bytes | None
    removed_directory: bool


class QuartoExporter(Protocol):
    def export_post(self, *, slug: str, title: str, metadata_values: dict, content: str,
                    published_at: datetime) -> QuartoExportResult: ...

    def remove_export(self, result: QuartoExportResult) -> None: ...

    def withdraw_post(self, slug: str) -> QuartoWithdrawalReceipt: ...

    def restore_withdrawal(self, receipt: QuartoWithdrawalReceipt) -> None: ...


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

    def _withdrawal_paths(self, slug: str) -> tuple[Path, Path]:
        if not SLUG_PATTERN.fullmatch(slug):
            raise QuartoExportError("No fue posible retirar el contenido Quarto.")
        posts = self._posts_root()
        directory = posts / slug
        source = directory / "index.qmd"
        try:
            if directory.is_symlink() or (directory.exists() and
                                          (not directory.is_dir() or directory.resolve(strict=True).parent != posts)):
                raise OSError("unsafe post directory")
            if source.is_symlink() or (source.exists() and
                                       (not source.is_file() or source.resolve(strict=True).parent != directory)):
                raise OSError("unsafe post source")
        except OSError:
            raise QuartoExportError("No fue posible retirar el contenido Quarto.") from None
        return directory, source

    def withdraw_post(self, slug: str) -> QuartoWithdrawalReceipt:
        directory, source = self._withdrawal_paths(slug)
        if not source.exists():
            logger.warning("quarto_withdraw_source_missing slug=%s", slug)
            return QuartoWithdrawalReceipt(slug, False, None, False)
        try:
            original = source.read_bytes()
            source.unlink()
        except OSError:
            raise QuartoExportError("No fue posible retirar el contenido Quarto.") from None
        removed_directory = False
        try:
            directory.rmdir()
            removed_directory = True
        except OSError:
            # Un directorio con imágenes u otros recursos debe permanecer intacto.
            pass
        return QuartoWithdrawalReceipt(slug, True, original, removed_directory)

    def restore_withdrawal(self, receipt: QuartoWithdrawalReceipt) -> None:
        if not receipt.existed:
            return
        directory, source = self._withdrawal_paths(receipt.slug)
        temporary: Path | None = None
        created_source = False
        try:
            if source.exists():
                raise OSError("source recreated during withdrawal")
            directory.mkdir(exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=directory, prefix=".restore-", suffix=".tmp", delete=False) as file:
                temporary = Path(file.name)
                file.write(receipt.original_bytes)
                file.flush()
                os.fsync(file.fileno())
            # El destino no debe sobrescribirse si otro proceso lo creó.
            with source.open("xb") as target:
                created_source = True
                target.write(temporary.read_bytes())
                target.flush()
                os.fsync(target.fileno())
            temporary.unlink()
            if source.read_bytes() != receipt.original_bytes:
                raise OSError("withdrawal restore verification failed")
        except OSError:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            if created_source:
                source.unlink(missing_ok=True)
            logger.exception("No se pudo restaurar el QMD tras fallar el archivado.")
            raise QuartoExportError("No fue posible restaurar el contenido Quarto.") from None
