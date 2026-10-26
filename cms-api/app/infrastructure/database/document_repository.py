"""Consultas y escrituras de Documents, sin reglas de lifecycle."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import DocumentContentType, DocumentStatus
from app.infrastructure.database.models import DocumentModel, TemplateModel


class SQLAlchemyDocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_quarto_publication(self) -> None:
        # Serializa renders de distintos POST entre workers mientras dura la
        # transacción. Un render completo comparte un único destino docs/.
        self._session.execute(select(func.pg_advisory_xact_lock(4850171141436910677)))

    def get_by_id(self, document_id: UUID, *, for_update: bool = False) -> DocumentModel | None:
        query = select(DocumentModel).where(DocumentModel.document_id == document_id)
        if for_update:
            query = query.with_for_update()
        return self._session.scalar(query)

    def get_by_slug(self, slug: str) -> DocumentModel | None:
        return self._session.scalar(select(DocumentModel).where(DocumentModel.slug == slug))

    def list_all(self, content_type: DocumentContentType | None = None, status: DocumentStatus | None = None) -> list[DocumentModel]:
        query = select(DocumentModel).order_by(DocumentModel.created_at, DocumentModel.document_id)
        if content_type is not None:
            query = query.where(DocumentModel.content_type == content_type.value)
        if status is not None:
            query = query.where(DocumentModel.status == status.value)
        return list(self._session.scalars(query))

    def get_templates(self, template_ids: set[UUID]) -> dict[UUID, TemplateModel]:
        # Lectura estable del contrato durante validación/escritura. El orden
        # común evita adquirir las mismas filas en distinto orden al cambiarlas.
        rows = self._session.scalars(
            select(TemplateModel).where(TemplateModel.template_id.in_(template_ids))
            .order_by(TemplateModel.template_id).with_for_update(read=True)
        )
        return {row.template_id: row for row in rows}

    def create(self, document: DocumentModel) -> None:
        self._session.add(document)
        self._session.flush()

    def update(self, document: DocumentModel) -> None:
        self._session.add(document)
        self._session.flush()

    def delete(self, document: DocumentModel) -> None:
        self._session.delete(document)
        self._session.flush()
