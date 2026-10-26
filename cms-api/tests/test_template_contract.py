"""Schemas, enums y OpenAPI del contrato simplificado."""

import unittest

from pydantic import ValidationError

from app.domain.enums import MetadataExpectedType, TemplateTargetType
from app.main import app
from app.schemas.template import MetadataContractItem, TemplateCreateRequest, TemplateUpdateRequest


class TemplateSchemaTests(unittest.TestCase):
    def test_target_enum_has_only_post_and_landing(self):
        self.assertEqual({value.value for value in TemplateTargetType}, {"POST", "LANDING"})

    def test_metadata_enum_has_only_four_types(self):
        self.assertEqual({value.value for value in MetadataExpectedType}, {"STRING", "INTEGER", "BOOLEAN", "DATE"})

    def test_each_expected_type_is_accepted(self):
        for expected in MetadataExpectedType:
            item = MetadataContractItem(field_key="fixture", expected_type=expected, is_required=True)
            self.assertEqual(item.expected_type, expected)

    def test_metadata_item_forbids_extra_fields(self):
        with self.assertRaises(ValidationError):
            MetadataContractItem(field_key="fixture", expected_type="STRING", is_required=True, extra="unexpected")

    def test_names_and_keys_are_trimmed_before_duplicate_validation(self):
        request = TemplateCreateRequest(
            name="  Nombre ficticio  ", target_type="POST", is_default=True, allow_published_edit=False,
            metadata_contract=[{"field_key": " category ", "expected_type": "STRING", "is_required": True}],
            layout_structure={},
        )
        self.assertEqual(request.name, "Nombre ficticio")
        self.assertEqual(request.metadata_contract[0].field_key, "category")

    def test_put_contains_only_required_editable_fields(self):
        self.assertEqual(set(TemplateUpdateRequest.model_fields), {"name", "is_default", "metadata_contract", "layout_structure"})
        self.assertTrue(all(field.is_required() for field in TemplateUpdateRequest.model_fields.values()))


class TemplateOpenAPITests(unittest.TestCase):
    def test_all_four_operations_declare_bearer(self):
        paths = app.openapi()["paths"]
        for path, methods in {
            "/api/v1/templates": {"post", "get"},
            "/api/v1/templates/{template_id}": {"put", "delete"},
        }.items():
            self.assertEqual(set(paths[path]), methods)
            for method in methods:
                self.assertEqual(paths[path][method]["security"], [{"AdminBearer": []}])

    def test_only_optional_target_filter_and_no_advanced_inputs(self):
        paths = app.openapi()["paths"]
        parameters = paths["/api/v1/templates"]["get"]["parameters"]
        self.assertEqual([(p["name"], p["in"], p["required"]) for p in parameters], [("target_type", "query", False)])
        for path, operations in paths.items():
            if path.startswith("/api/v1/templates"):
                for operation in operations.values():
                    names = {p["name"] for p in operation.get("parameters", [])}
                    self.assertFalse(names & {"cursor", "limit", "Idempotency-Key", "fallback_template_id"})
        self.assertNotIn("requestBody", paths["/api/v1/templates/{template_id}"]["delete"])

    def test_request_response_schemas_are_public_contracts(self):
        specification = app.openapi()
        paths = specification["paths"]
        for path, method, name in (
            ("/api/v1/templates", "post", "TemplateCreateRequest"),
            ("/api/v1/templates/{template_id}", "put", "TemplateUpdateRequest"),
        ):
            schema = paths[path][method]["requestBody"]["content"]["application/json"]["schema"]
            self.assertEqual(schema["$ref"], "#/components/schemas/" + name)
            self.assertFalse(specification["components"]["schemas"][name]["additionalProperties"])
        self.assertNotIn("TemplateModel", specification["components"]["schemas"])
