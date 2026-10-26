"""Puerto mínimo de persistencia administrativa, sin operaciones de gestión."""

from typing import Protocol
from datetime import datetime
from uuid import UUID

from app.infrastructure.database.models.admin_user import AdminUserModel


class AdminUserRepository(Protocol):
    def get_by_id(self, user_id: UUID) -> AdminUserModel | None: ...

    def get_by_username(self, username: str) -> AdminUserModel | None: ...

    def exists_by_username(self, username: str) -> bool: ...

    def create(self, admin_user: AdminUserModel) -> None: ...

    def update_last_login(self, user_id: UUID, timestamp: datetime) -> bool: ...
