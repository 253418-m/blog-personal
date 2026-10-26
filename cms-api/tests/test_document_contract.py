"""Contrato público y validación de metadatos, sin conexiones globales."""

import unittest

from app.core.exceptions import BusinessRuleViolation
from app.main import app
from app.services.metadata_validation import validate_metadata


class MetadataValidationTests(unittest.TestCase):
    def validate(self, kind, value):
        validate_metadata([{"field_key": "value", "expected_type": kind, "is_required": True}],
                          {"value": value}, True)

    def test_exact_types(self):
        for kind, value in (("STRING", "texto"), ("INTEGER", 0), ("BOOLEAN", False), ("DATE", "2024-02-29")):
            with self.subTest(kind=kind):
                self.validate(kind, value)

    def test_boolean_is_not_integer_and_no_type_coercion(self):
        for kind, value in (("INTEGER", True), ("INTEGER", "3"), ("INTEGER", 3.0),
                            ("BOOLEAN", 1), ("BOOLEAN", "false"), ("STRING", 7), ("STRING", None)):
            with self.subTest(kind=kind, value=value), self.assertRaises(BusinessRuleViolation):
                self.validate(kind, value)

    def test_date_requires_iso_calendar_date(self):
        for value in ("2023-02-29", "20260101", "2026-W01-1", "2026-1-01", "2026-01-01T00:00:00Z", None):
            with self.subTest(value=value), self.assertRaises(BusinessRuleViolation):
                self.validate("DATE", value)

    def test_required_fields_differ_between_draft_and_publication(self):
        contract = [{"field_key": "title", "expected_type": "STRING", "is_required": True}]
        validate_metadata(contract, {}, False)
        with self.assertRaises(BusinessRuleViolation):
            validate_metadata(contract, {}, True)

    def test_optional_missing_is_valid_but_unknown_field_is_not(self):
        contract = [{"field_key": "title", "expected_type": "STRING", "is_required": False}]
        validate_metadata(contract, {}, True)
        with self.assertRaises(BusinessRuleViolation):
            validate_metadata(contract, {"unknown": "value"}, False)


class DocumentOpenAPITests(unittest.TestCase):
    def test_exact_seven_protected_operations(self):
        schema = app.openapi()
        actual = {(path, method) for path, operations in schema["paths"].items()
                  if path.startswith("/api/v1/documents") for method in operations}
        base = "/api/v1/documents"
        self.assertEqual(actual, {(base, "post"), (base, "get"), (base + "/{document_id}", "get"),
                                 (base + "/{document_id}", "put"), (base + "/{document_id}", "delete"),
                                 (base + "/{document_id}/publish", "post"),
                                 (base + "/{document_id}/archive", "post")})
        for path, method in actual:
            self.assertTrue(schema["paths"][path][method]["security"])
        for action in ("publish", "archive"):
            self.assertNotIn("requestBody", schema["paths"][base + "/{document_id}/" + action]["post"])

    def test_active_enums_and_public_fields(self):
        schemas = app.openapi()["components"]["schemas"]
        self.assertEqual(schemas["DocumentStatus"]["enum"], ["BORRADOR", "PUBLICADO", "ARCHIVADO"])
        self.assertEqual(schemas["DocumentContentType"]["enum"], ["POST", "LANDING"])
        self.assertEqual(set(schemas["DocumentResponse"]["properties"]), {
            "document_id", "title", "slug", "content_type", "status", "template_id", "metadata_values",
            "content", "created_at", "updated_at", "published_at"})

    def test_requests_forbid_extra_fields_and_filters_are_only_type_and_status(self):
        schema = app.openapi()
        for name in ("DocumentCreateRequest", "DocumentUpdateRequest"):
            self.assertFalse(schema["components"]["schemas"][name]["additionalProperties"])
        parameters = schema["paths"]["/api/v1/documents"]["get"]["parameters"]
        self.assertEqual({p["name"] for p in parameters}, {"content_type", "status"})
