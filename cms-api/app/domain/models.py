"""Modelos internos parciales; no constituyen contratos HTTP completos.

Solo se declaran campos inequívocos. Identidad, relaciones y demás campos
permanecen CONTRACT_PENDING. Las invariantes todavía no están implementadas.
"""

from dataclasses import dataclass

from app.domain.enums import DocumentStatus


@dataclass
class Template:
    """Fragmento conocido de Template; sin políticas de mutación implementadas."""

    is_default: bool
    target_type: str
    allow_published_edit: bool


@dataclass
class Document:
    """Fragmento conocido de Document; sin estado inicial predeterminado."""

    slug: str
    status: DocumentStatus


class CanvasBlock:
    """TODO(CONTRACT_PENDING): definir estructura del bloque y sus campos."""


class ReviewReport:
    """TODO(CONTRACT_PENDING): definir campos del dictamen editorial."""


class MetricSnapshot:
    """TODO(CONTRACT_PENDING): definir métricas, tipos y unidades."""


class PreviewSession:
    """TODO(CONTRACT_PENDING): definir campos y ciclo de vida de la sesión."""
