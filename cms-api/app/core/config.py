"""Configuración central: entorno del proceso sobre el .env local del backend."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
DEFAULT_QUARTO_PROJECT_ROOT = ENV_FILE.parent.parent


class Settings(BaseSettings):
    """Valores inmutables; la URL sensible se excluye de repr y serialización."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_url: SecretStr = Field(repr=False, exclude=True)
    jwt_secret_key: SecretStr = Field(repr=False, exclude=True)
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=30, gt=0)
    quarto_project_root: Path = DEFAULT_QUARTO_PROJECT_ROOT
    quarto_executable: str = "quarto"
    quarto_render_timeout_seconds: int = Field(default=120, gt=0)

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET_KEY debe tener al menos 32 bytes.")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except (ArgumentError, TypeError, ValueError):
            raise ValueError("DATABASE_URL debe ser una URL SQLAlchemy válida.") from None
        if url.drivername != "postgresql+psycopg":
            raise ValueError("DATABASE_URL debe usar el driver postgresql+psycopg.")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Carga una vez por proceso; reinicia el proceso para releer el .env."""
    try:
        return Settings()
    except ValidationError as error:
        errors = error.errors(include_input=False, include_context=False)
        if any(e["loc"] == ("database_url",) and e["type"] == "missing" for e in errors):
            raise RuntimeError("Define DATABASE_URL en el entorno o en el .env local del backend.") from None
        if any(e["loc"] == ("jwt_secret_key",) and e["type"] == "missing" for e in errors):
            raise RuntimeError("Define JWT_SECRET_KEY en el entorno o en el .env local del backend.") from None
        raise RuntimeError("Configuración inválida; revisa DATABASE_URL, JWT_* y APP_*.") from None
    except (SettingsError, OSError):
        raise RuntimeError("No se pudo cargar la configuración del entorno o del .env local.") from None


def get_database_url() -> str:
    """Devuelve la URL únicamente al consumidor de persistencia, sin imprimirla."""
    return get_settings().database_url.get_secret_value()
