"""Configuración aislada en archivos temporales; nunca modificar el .env real."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.core.config import ENV_FILE, Settings, get_database_url, get_settings


class SettingsTests(unittest.TestCase):
    file_url = "postgresql+psycopg://fixture:file-secret@localhost:5432/fixture_db"
    environment_url = "postgresql+psycopg://fixture:environment-secret@localhost:5432/fixture_db"
    jwt_fixture = "test-only-config-signing-key-not-for-production-0000000000000000"

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env_file = Path(self.directory.name) / ".env"
        self.env_file.write_text(
            "DATABASE_URL=" + self.file_url + "\nJWT_SECRET_KEY=" + self.jwt_fixture + "\n",
            encoding="utf-8",
        )
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.config = patch.dict(Settings.model_config, {"env_file": self.env_file})
        self.config.start()
        self.addCleanup(self.config.stop)
        get_settings.cache_clear()
        self.addCleanup(get_settings.cache_clear)

    def test_loads_database_url_from_controlled_env_file(self):
        settings = Settings()
        self.assertTrue(settings.database_url.get_secret_value() == self.file_url)

    def test_real_environment_takes_precedence_over_env_file(self):
        os.environ["DATABASE_URL"] = self.environment_url
        self.assertTrue(get_database_url() == self.environment_url)

    def test_missing_database_url_raises_clear_error_without_fallback(self):
        self.env_file.unlink()
        with self.assertRaisesRegex(RuntimeError, "Define DATABASE_URL.*entorno.*.env"):
            get_database_url()

    def test_get_database_url_returns_expected_sqlalchemy_string(self):
        result = get_database_url()
        self.assertIsInstance(result, str)
        self.assertTrue(result == self.file_url)

    def test_secret_is_excluded_from_repr_and_serialization(self):
        settings = get_settings()
        for rendered in (repr(settings), str(settings), settings.model_dump_json()):
            self.assertTrue("file-secret" not in rendered)
            self.assertTrue(self.file_url not in rendered)
            self.assertTrue(self.jwt_fixture not in rendered)
        self.assertNotIn("database_url", settings.model_dump())
        self.assertNotIn("jwt_secret_key", settings.model_dump())

    def test_invalid_configuration_errors_do_not_expose_input(self):
        os.environ["APP_PORT"] = self.environment_url
        with self.assertRaises(ValidationError) as raised:
            Settings()
        self.assertTrue("environment-secret" not in str(raised.exception))
        self.assertTrue(self.environment_url not in str(raised.exception))
        with self.assertRaises(RuntimeError) as safe:
            get_settings()
        self.assertTrue("environment-secret" not in str(safe.exception))

    def test_invalid_or_blank_url_does_not_fall_back_to_env_file(self):
        for value in ("", "not-a-url-with-fixture-secret", "sqlite:///fixture.db"):
            get_settings.cache_clear()
            os.environ["DATABASE_URL"] = value
            with self.assertRaisesRegex(RuntimeError, "Configuración inválida"):
                get_database_url()

    def test_settings_are_cached_until_cache_is_cleared(self):
        first = get_settings()
        os.environ["DATABASE_URL"] = self.environment_url
        self.assertIs(get_settings(), first)
        self.assertTrue(get_database_url() == self.file_url)
        get_settings.cache_clear()
        self.assertTrue(get_database_url() == self.environment_url)

    def test_unknown_dotenv_keys_are_ignored_and_app_options_are_loaded(self):
        with self.env_file.open("a", encoding="utf-8") as stream:
            stream.write("POSTGRES_PASSWORD=unused-fixture\nAPP_ENV=test\nAPP_PORT=8012\n")
        settings = get_settings()
        self.assertEqual(settings.app_env, "test")
        self.assertEqual(settings.app_port, 8012)
        self.assertFalse(hasattr(settings, "postgres_password"))

    def test_default_env_path_is_absolute_and_relative_to_the_backend_module(self):
        from app.core import config

        self.assertTrue(ENV_FILE.is_absolute())
        self.assertEqual(ENV_FILE, Path(config.__file__).resolve().parents[2] / ".env")

    def test_settings_are_immutable(self):
        settings = get_settings()
        with self.assertRaises(ValidationError):
            settings.app_port = 9999

    def test_jwt_secret_is_required_without_fallback(self):
        self.env_file.write_text("DATABASE_URL=" + self.file_url + "\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Define JWT_SECRET_KEY"):
            get_settings()

    def test_jwt_environment_secret_has_precedence(self):
        alternate = "alternate-test-only-signing-key-000000000000000000000000000000"
        os.environ["JWT_SECRET_KEY"] = alternate
        self.assertTrue(get_settings().jwt_secret_key.get_secret_value() == alternate)

    def test_short_jwt_secret_is_rejected_without_exposure(self):
        os.environ["JWT_SECRET_KEY"] = "short-test-fixture"
        with self.assertRaises(RuntimeError) as raised:
            get_settings()
        self.assertNotIn("short-test-fixture", str(raised.exception))

    def test_jwt_algorithm_is_only_hs256(self):
        os.environ["JWT_ALGORITHM"] = "HS512"
        with self.assertRaisesRegex(RuntimeError, "Configuración inválida"):
            get_settings()

    def test_jwt_defaults_are_hs256_and_thirty_minutes(self):
        settings = get_settings()
        self.assertEqual(settings.jwt_algorithm, "HS256")
        self.assertEqual(settings.jwt_access_token_expire_minutes, 30)

    def test_jwt_ttl_is_configurable(self):
        os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = "7"
        self.assertEqual(get_settings().jwt_access_token_expire_minutes, 7)

    def test_jwt_ttl_must_be_positive(self):
        for value in ("0", "-1"):
            get_settings.cache_clear()
            os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = value
            with self.assertRaises(RuntimeError):
                get_settings()
