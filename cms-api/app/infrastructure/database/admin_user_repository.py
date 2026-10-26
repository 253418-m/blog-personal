"""Repositorio SQLAlchemy; el caso de uso es dueño de la transacción."""

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models.admin_user import AdminUserModel


class SQLAlchemyAdminUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

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
