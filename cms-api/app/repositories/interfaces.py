"""Puertos mínimos sin almacenamiento ni firmas de operaciones inventadas.

Los protocolos son marcadores vacíos, todavía no contratos de persistencia
utilizables. Sus operaciones se definirán junto con cada caso de uso.
"""

from typing import Protocol


class TemplateRepository(Protocol):
    """TODO(CONTRACT_PENDING): definir operaciones e identidad de Template."""


class DocumentRepository(Protocol):
    """TODO(CONTRACT_PENDING): definir operaciones e identidad de Document."""
