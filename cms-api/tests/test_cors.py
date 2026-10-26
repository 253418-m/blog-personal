"""Solo los orígenes administrativos configurados pueden leer la API desde navegador."""

import unittest

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app


class CorsTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_development_origins_allow_authorization_preflight(self):
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            with self.subTest(origin=origin):
                response = self.client.options(
                    "/api/v1/documents",
                    headers={"Origin": origin, "Access-Control-Request-Method": "GET",
                             "Access-Control-Request-Headers": "authorization,content-type"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["access-control-allow-origin"], origin)
                allowed = response.headers["access-control-allow-headers"].lower()
                self.assertIn("authorization", allowed)
                self.assertIn("content-type", allowed)

    def test_unlisted_origin_is_not_allowed(self):
        response = self.client.options(
            "/api/v1/documents",
            headers={"Origin": "https://unlisted.example", "Access-Control-Request-Method": "GET"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_allowed_origin_gets_cors_header_on_auth_error(self):
        response = self.client.get(
            "/api/v1/auth/me", headers={"Origin": "http://localhost:5173"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_settings_accept_explicit_admin_origin_and_reject_wildcard(self):
        settings = Settings(
            _env_file=None,
            database_url="postgresql+psycopg://fixture@localhost:5432/cms_core",
            jwt_secret_key="fixture-secret-with-more-than-thirty-two-bytes",
            cors_allowed_origins="https://admin.example",
        )
        self.assertEqual(settings.cors_origins, ["https://admin.example"])
        with self.assertRaises(ValueError):
            Settings(
                _env_file=None,
                database_url="postgresql+psycopg://fixture@localhost:5432/cms_core",
                jwt_secret_key="fixture-secret-with-more-than-thirty-two-bytes",
                cors_allowed_origins="*",
            )


if __name__ == "__main__":
    unittest.main()
