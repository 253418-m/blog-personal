"""Documento persistente, sin ejecutar las reglas editoriales del dominio."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import DocumentStatus
from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.infrastructure.database.models.canvas_block import CanvasBlockModel
    from app.infrastructure.database.models.review_report import ReviewReportModel
    from app.infrastructure.database.models.template import TemplateModel


class DocumentModel(Base):
    """El último dictamen se consultará en review_reports por audited_at DESC."""

    __tablename__ = "documents"
    __table_args__ = (
        PrimaryKeyConstraint("document_id", name="pk_documents"),
        UniqueConstraint("slug", name="uq_documents_slug"),
        Index("ix_documents_template_id", "template_id"),
        Index("ix_documents_status", "status"),
    )

    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    slug: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    # CONTRACT_PENDING: no cerrar content_type con un catálogo parcial.
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum: [status.value for status in enum],
        ),
        nullable=False,
    )
    template_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "templates.template_id",
            name="fk_documents_template_id_templates",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    frozen_template: Mapped[Any | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    metadata_values: Mapped[Any | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    template: Mapped[TemplateModel] = relationship(
        "TemplateModel", back_populates="documents", cascade="save-update, merge"
    )
    canvas_blocks: Mapped[list[CanvasBlockModel]] = relationship(
        "CanvasBlockModel",
        back_populates="document",
        order_by="CanvasBlockModel.order_index",
        cascade="save-update, merge",
        passive_deletes="all",
    )
    review_reports: Mapped[list[ReviewReportModel]] = relationship(
        "ReviewReportModel",
        back_populates="document",
        order_by="ReviewReportModel.audited_at.desc()",
        cascade="save-update, merge",
        passive_deletes="all",
    )
