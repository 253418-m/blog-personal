"""Repositorio SQLAlchemy; el caso de uso es dueño de la transacción."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from app.infrastructure.database.models.admin_user import AdminUserModel


class SQLAlchemyAdminUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: UUID) -> AdminUserModel | None:
        return self._session.get(AdminUserModel, user_id)

    def get_by_username(self, username: str) -> AdminUserModel | None:
        return self._session.scalar(
            select(AdminUserModel).where(AdminUserModel.username == username)
        )

    def exists_by_username(self, username: str) -> bool:
        return bool(self._session.scalar(
            select(exists().where(AdminUserModel.username == username))
        ))

    def create(self, admin_user: AdminUserModel) -> None:
        self._session.add(admin_user)
        self._session.flush()

    def update_last_login(self, user_id: UUID, timestamp: datetime) -> bool:
        """Actualiza solo si la cuenta sigue activa al ejecutar la escritura."""
        result = self._session.execute(
            update(AdminUserModel)
            .where(AdminUserModel.user_id == user_id, AdminUserModel.is_active.is_(True))
            .values(last_login_at=timestamp)
        )
        self._session.flush()
        return result.rowcount == 1
