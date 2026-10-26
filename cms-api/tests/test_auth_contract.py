"""Schemas y OpenAPI sin llamadas HTTP ni credenciales reales."""

import unittest

from app.main import app
from app.schemas.auth import CurrentAdminResponse, LoginRequest, TokenResponse


class AuthContractTests(unittest.TestCase):
    def test_login_request_repr_and_serialization_hide_password(self):
        request = LoginRequest(username="schema-fixture", password="fictitious-schema-password")
        self.assertTrue("fictitious-schema-password" not in repr(request))
        self.assertNotIn("password", request.model_dump())

    def test_current_admin_schema_has_only_public_fields(self):
        self.assertEqual(set(CurrentAdminResponse.model_fields), {"user_id", "username", "is_active"})

    def test_token_response_repr_does_not_expose_token(self):
        response = TokenResponse(access_token="fictitious-schema-token", expires_in=1800)
        self.assertTrue("fictitious-schema-token" not in repr(response))

    def test_openapi_contains_only_the_two_auth_paths(self):
        self.assertEqual(set(app.openapi()["paths"]), {"/api/v1/auth/login", "/api/v1/auth/me"})

    def test_login_is_public_json_and_me_has_http_bearer_security(self):
        specification = app.openapi()
        login = specification["paths"]["/api/v1/auth/login"]["post"]
        me = specification["paths"]["/api/v1/auth/me"]["get"]
        self.assertEqual(set(login["requestBody"]["content"]), {"application/json"})
        self.assertFalse(login.get("security"))
        self.assertEqual(me["security"], [{"AdminBearer": []}])
        security = specification["components"]["securitySchemes"]["AdminBearer"]
        self.assertEqual(security["type"], "http")
        self.assertEqual(security["scheme"], "bearer")
        self.assertEqual(security["bearerFormat"], "JWT")
