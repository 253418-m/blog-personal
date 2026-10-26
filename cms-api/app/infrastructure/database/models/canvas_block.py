"""Bloque ordenado que pertenece a la composición de un documento."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base

if TYPE_CHECKING:
    from app.infrastructure.database.models.document import DocumentModel


class CanvasBlockModel(Base):
    """El servicio decidirá si el documento puede eliminarse antes del DELETE."""

    __tablename__ = "canvas_blocks"
    __table_args__ = (
        PrimaryKeyConstraint("block_id", name="pk_canvas_blocks"),
        UniqueConstraint(
            "document_id",
            "order_index",
            name="uq_canvas_blocks_document_id_order_index",
        ),
    )

    block_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "documents.document_id",
            name="fk_canvas_blocks_document_id_documents",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    # CONTRACT_PENDING: faltan los valores completos de block_type.
    block_type: Mapped[str] = mapped_column(String, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_payload: Mapped[Any] = mapped_column(JSONB, nullable=False)
    style_config: Mapped[Any | None] = mapped_column(
        JSONB(none_as_null=True), nullable=True
    )

    document: Mapped[DocumentModel] = relationship(
        "DocumentModel", back_populates="canvas_blocks", cascade="save-update, merge"
    )
