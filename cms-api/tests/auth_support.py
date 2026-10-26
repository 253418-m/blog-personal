"""Datos ficticios compartidos; ninguna credencial proviene del administrador real."""

from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID

import jwt
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.infrastructure.database.models import AdminUserModel
from app.services.auth_service import AuthService
from tests.postgresql import IsolatedAdminPostgreSQLTestCase


AUTH_USER_ID = UUID("0195e4f0-3000-7000-8000-000000000001")
AUTH_MISSING_ID = UUID("0195e4f0-3000-7000-8000-0000000000ff")
AUTH_USERNAME = "http-auth-test-fixture"
AUTH_PASSWORD = "test-only-auth-password"
JWT_TEST_SECRET = "fictitious-test-signing-key-not-for-production-" * 2
FIXTURE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def auth_settings(**overrides) -> Settings:
    values = {
        "database_url": "postgresql+psycopg://fixture@localhost:5432/cms_core",
        "jwt_secret_key": JWT_TEST_SECRET,
        "jwt_algorithm": "HS256",
        "jwt_access_token_expire_minutes": 30,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@lru_cache(maxsize=1)
def fixture_password_hash() -> str:
    return hash_password(AUTH_PASSWORD)


def signed_fixture_token(*, algorithm="HS256", secret=JWT_TEST_SECRET, **overrides) -> str:
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {"sub": str(AUTH_USER_ID), "iat": now, "exp": now + 1800, "type": "access"}
    claims.update(overrides)
    return jwt.encode(claims, None if algorithm == "none" else secret, algorithm=algorithm)


class AuthPostgreSQLTestCase(IsolatedAdminPostgreSQLTestCase):
    def setUp(self):
        super().setUp()
        self.settings = auth_settings()
        self.connection.execute(AdminUserModel.__table__.insert().values(
            user_id=AUTH_USER_ID,
            username=AUTH_USERNAME,
            password_hash=fixture_password_hash(),
            is_active=True,
            created_at=FIXTURE_TIME,
            updated_at=FIXTURE_TIME,
            last_login_at=None,
        ))
        self.service = AuthService(self.session_factory)

    def session_factory(self):
        return Session(
            bind=self.connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
