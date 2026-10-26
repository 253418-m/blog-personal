"""Plantilla persistente; sus invariantes transaccionales quedan en services."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.infrastructure.database.models.document import DocumentModel


class TemplateModel(Base):
    """UUIDv7, timestamps y políticas se proporcionarán desde la aplicación."""

    __tablename__ = "templates"
    __table_args__ = (
        PrimaryKeyConstraint("template_id", name="pk_templates"),
        UniqueConstraint("name", name="uq_templates_name"),
    )

    template_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    # CONTRACT_PENDING: todavía no se conoce el catálogo completo de target_type.
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_published_edit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metadata_contract: Mapped[Any] = mapped_column(JSONB, nullable=False)
    layout_structure: Mapped[Any] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    documents: Mapped[list[DocumentModel]] = relationship(
        "DocumentModel",
        back_populates="template",
        cascade="save-update, merge",
        passive_deletes="all",
    )
