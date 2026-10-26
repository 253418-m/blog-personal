"""Puerto mínimo de persistencia administrativa, sin operaciones de gestión."""

from typing import Protocol

from app.infrastructure.database.models.admin_user import AdminUserModel


class AdminUserRepository(Protocol):
    def get_by_username(self, username: str) -> AdminUserModel | None: ...

    def exists_by_username(self, username: str) -> bool: ...

    def create(self, admin_user: AdminUserModel) -> None: ...
