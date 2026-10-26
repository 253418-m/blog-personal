"""Caso de uso explícito para crear exclusivamente el primer administrador."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.core.security import PasswordHasher
from app.infrastructure.database.admin_user_repository import SQLAlchemyAdminUserRepository
from app.infrastructure.database.models.admin_user import AdminUserModel
from app.repositories.admin_user import AdminUserRepository


MIN_PASSWORD_LENGTH = 12
# Namespace estable del bloqueo transaccional de este único caso de uso.
BOOTSTRAP_LOCK_NAMESPACE = 0x434D53
BOOTSTRAP_LOCK_ID = 1


class AdminBootstrapError(Exception):
    """Error seguro para presentar en la terminal, sin datos de persistencia."""


class BootstrapValidationError(AdminBootstrapError):
    pass


class UsernameAlreadyExists(AdminBootstrapError):
    pass


class BootstrapAlreadyCompleted(AdminBootstrapError):
    pass


class BootstrapStorageError(AdminBootstrapError):
    pass


@dataclass(frozen=True)
class CreatedAdmin:
    """Resultado sin contraseña ni hash."""

    user_id: UUID
    username: str


class AdminBootstrapService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._hasher = password_hasher or PasswordHasher()

    def create_first_admin(self, username: str, password: str) -> CreatedAdmin:
        if not isinstance(username, str) or not username.strip():
            raise BootstrapValidationError("El username no puede estar vacío.")
        username = username.strip()
        if not isinstance(password, str) or not password.strip():
            raise BootstrapValidationError("La contraseña no puede estar vacía.")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise BootstrapValidationError(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
            )

        try:
            with self._session_factory() as session, session.begin():
                # READ COMMITTED permite ver el resultado del bootstrap anterior
                # después de esperar el bloqueo, incluso con usernames distintos.
                if session.connection().get_isolation_level() != "READ COMMITTED":
                    raise BootstrapStorageError("El bootstrap requiere READ COMMITTED.")
                session.execute(select(func.pg_advisory_xact_lock(
                    BOOTSTRAP_LOCK_NAMESPACE, BOOTSTRAP_LOCK_ID
                )))
                repository: AdminUserRepository = SQLAlchemyAdminUserRepository(session)
                if repository.exists_by_username(username):
                    raise UsernameAlreadyExists("El username ya existe; no se modificó.")
                if session.scalar(select(exists().select_from(AdminUserModel))):
                    raise BootstrapAlreadyCompleted("El bootstrap inicial ya fue completado.")

                now = datetime.now(timezone.utc)
                admin = AdminUserModel(
                    user_id=uuid7(),
                    username=username,
                    password_hash=self._hasher.hash_password(password),
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                    last_login_at=None,
                )
                repository.create(admin)
                result = CreatedAdmin(user_id=admin.user_id, username=admin.username)
            return result
        except IntegrityError as error:
            if getattr(error.orig, "sqlstate", None) == "23505":
                raise UsernameAlreadyExists("El username ya existe; no se modificó.") from None
            raise BootstrapStorageError("No se pudo guardar el administrador.") from None
        except SQLAlchemyError:
            raise BootstrapStorageError("No se pudo completar el bootstrap en la base de datos.") from None
