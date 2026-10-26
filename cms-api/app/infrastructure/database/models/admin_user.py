"""Persistencia administrativa; hashing y autenticación pertenecen a otra fase."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, PrimaryKeyConstraint, String, Text, UniqueConstraint, true
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class AdminUserModel(Base):
    """Solo almacena hashes; UUIDv7 y timestamps los aportará la aplicación."""

    __tablename__ = "admin_users"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", name="pk_admin_users"),
        UniqueConstraint("username", name="uq_admin_users_username"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, nullable=False
    )
    username: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
