"""Autenticación independiente de HTTP; confirma last_login antes de devolver éxito."""

from collections.abc import Callable
from datetime import datetime, timezone
import secrets

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.infrastructure.database.admin_user_repository import SQLAlchemyAdminUserRepository
from app.infrastructure.database.models.admin_user import AdminUserModel
from app.repositories.admin_user import AdminUserRepository


# Se genera una vez con material ficticio aleatorio y nunca se persiste ni se registra.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


class InvalidCredentials(Exception):
    """Mismo resultado para usuario ausente, password incorrecta o cuenta inactiva."""


class AuthenticationUnavailable(Exception):
    """Error de persistencia seguro para la capa de transporte."""


class AuthService:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def authenticate(self, username: str, password: str) -> AdminUserModel:
        try:
            with self._session_factory() as session, session.begin():
                repository: AdminUserRepository = SQLAlchemyAdminUserRepository(session)
                admin = repository.get_by_username(username.strip())
                matches = verify_password(password, admin.password_hash if admin else _DUMMY_HASH)
                if admin is None or not matches or not admin.is_active:
                    raise InvalidCredentials("Credenciales inválidas.")
                if not repository.update_last_login(admin.user_id, datetime.now(timezone.utc)):
                    raise InvalidCredentials("Credenciales inválidas.")
                # Un resultado separado de la Session conserva solo atributos ya
                # cargados; la salida HTTP utiliza schemas explícitos sin el hash.
                session.expunge(admin)
            return admin
        except SQLAlchemyError:
            raise AuthenticationUnavailable("No se pudo completar la autenticación.") from None
