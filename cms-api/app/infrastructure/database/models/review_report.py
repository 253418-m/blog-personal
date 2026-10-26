"""Dictamen editorial asociado a un documento, sin información duplicada."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.infrastructure.database.models.document import DocumentModel


class ReviewReportModel(Base):
    """audited_at permite recuperar el dictamen más reciente sin latest_review."""

    __tablename__ = "review_reports"

    report_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "documents.document_id",
            name="fk_review_reports_document_id_documents",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    findings: Mapped[Any] = mapped_column(JSONB, nullable=False)
    audited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("report_id", name="pk_review_reports"),
        Index(
            "ix_review_reports_document_id_audited_at", "document_id", audited_at.desc()
        ),
    )

    document: Mapped[DocumentModel] = relationship(
        "DocumentModel", back_populates="review_reports", cascade="save-update, merge"
    )
