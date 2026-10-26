"""Validación compartida para guardar borradores y publicar contenido."""

from datetime import date
import re
from typing import Any

from app.core.exceptions import BusinessRuleViolation


def validate_metadata(
    metadata_contract: list[dict[str, Any]],
    metadata_values: dict[str, Any],
    require_required_fields: bool,
) -> None:
    fields = {item["field_key"]: item for item in metadata_contract}
    if metadata_values.keys() - fields.keys():
        raise BusinessRuleViolation("metadata_values contiene campos no definidos en la Template.")
    for key, field in fields.items():
        if key not in metadata_values:
            if require_required_fields and field["is_required"]:
                raise BusinessRuleViolation("Faltan metadatos requeridos para publicar.")
            continue
        value = metadata_values[key]
        expected = field["expected_type"]
        valid = (
            (expected == "STRING" and isinstance(value, str))
            or (expected == "INTEGER" and type(value) is int)
            or (expected == "BOOLEAN" and type(value) is bool)
        )
        if expected == "DATE" and isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            try:
                date.fromisoformat(value)
                valid = True
            except ValueError:
                valid = False
        if not valid:
            raise BusinessRuleViolation("Un metadato no cumple el tipo definido en la Template.")
