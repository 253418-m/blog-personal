"""Valores definidos expresamente por el contrato existente."""

from enum import Enum


class DocumentStatus(str, Enum):
    BORRADOR = "BORRADOR"
    PUBLICADO = "PUBLICADO"
    ARCHIVADO = "ARCHIVADO"


class DocumentContentType(str, Enum):
    POST = "POST"
    LANDING = "LANDING"


class TemplateTargetType(str, Enum):
    POST = "POST"
    LANDING = "LANDING"


class MetadataExpectedType(str, Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
