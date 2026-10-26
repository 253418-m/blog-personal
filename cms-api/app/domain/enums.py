"""Valores definidos expresamente por el contrato existente."""

from enum import Enum


class DocumentStatus(str, Enum):
    BORRADOR = "BORRADOR"
    EN_REVISION = "EN_REVISION"
    PUBLICADO = "PUBLICADO"
    ARCHIVADO = "ARCHIVADO"


# TODO(CONTRACT_PENDING): valores completos de target_type; no crear un enum aún.
