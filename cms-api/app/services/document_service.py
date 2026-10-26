"""Reglas POST/LANDING y publicación con export, render y compensación."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.core.exceptions import BusinessRuleViolation, DomainConflict, DomainError, ResourceNotFound
from app.domain.enums import DocumentContentType, DocumentStatus
from app.infrastructure.database.document_repository import SQLAlchemyDocumentRepository
from app.infrastructure.database.models import DocumentModel, TemplateModel
from app.repositories.interfaces import DocumentRepository
from app.schemas.document import DocumentCreateRequest, DocumentResponse, DocumentUpdateRequest
from app.services.metadata_validation import validate_metadata
from app.services.quarto_export import QuartoCollisionError, QuartoExporter, QuartoExportError
from app.services.quarto_render import QuartoRenderError, QuartoRenderService


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DocumentStorageUnavailable(DomainError):
    """Fallo operativo seguro para la capa HTTP."""


class QuartoExportUnavailable(DomainError):
    """Fallo seguro de exportación o compensación."""


class QuartoRenderUnavailable(DomainError):
    """Fallo seguro de render o restauración de docs/."""


class DocumentService:
    def __init__(self, session_factory: Callable[[], Session], quarto_exporter: QuartoExporter,
                 quarto_render_service: QuartoRenderService) -> None:
        self._session_factory = session_factory
        self._quarto_exporter = quarto_exporter
        self._quarto_render_service = quarto_render_service

    @contextmanager
    def _repository(self) -> Iterator[DocumentRepository]:
        try:
            with self._session_factory() as session, session.begin():
                yield SQLAlchemyDocumentRepository(session)
        except IntegrityError as error:
            state = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if state == "23505" and constraint == "uq_documents_slug":
                raise DomainConflict("Ya existe un Document con ese slug.") from None
            if state == "23503" and constraint == "fk_documents_template_id_templates":
                raise ResourceNotFound("Template no encontrada.") from None
            raise DocumentStorageUnavailable("Servicio de Documents no disponible.") from None
        except SQLAlchemyError:
            raise DocumentStorageUnavailable("Servicio de Documents no disponible.") from None

    @staticmethod
    def _require(repository: DocumentRepository, document_id: UUID, *, write: bool = False) -> DocumentModel:
        document = repository.get_by_id(document_id, for_update=write)
        if document is None:
            raise ResourceNotFound("Document no encontrado.")
        return document

    @staticmethod
    def _template(templates: dict[UUID, TemplateModel], template_id: UUID, content_type: str) -> TemplateModel:
        template = templates.get(template_id)
        if template is None:
            raise ResourceNotFound("Template no encontrada.")
        if template.target_type != content_type:
            raise BusinessRuleViolation("La Template no coincide con el content_type del Document.")
        return template

    @staticmethod
    def _unique_slug(repository: DocumentRepository, slug: str, document_id: UUID | None = None) -> None:
        other = repository.get_by_slug(slug)
        if other is not None and other.document_id != document_id:
            raise DomainConflict("Ya existe un Document con ese slug.")

    @staticmethod
    def _validate(template: TemplateModel, metadata: dict, content: str, *, published: bool) -> None:
        validate_metadata(template.metadata_contract, metadata, require_required_fields=published)
        if published and not content.strip():
            raise BusinessRuleViolation("El contenido no puede estar vacío al publicar.")

    def create_document(self, request: DocumentCreateRequest) -> DocumentResponse:
        with self._repository() as repository:
            template = self._template(repository.get_templates({request.template_id}), request.template_id, request.content_type)
            self._validate(template, request.metadata_values, request.content, published=False)
            self._unique_slug(repository, request.slug)
            now = datetime.now(timezone.utc)
            document = DocumentModel(
                **request.model_dump(mode="python"), document_id=uuid7(), status=DocumentStatus.BORRADOR,
                created_at=now, updated_at=now, published_at=None,
            )
            repository.create(document)
            return DocumentResponse.model_validate(document)

    def list_documents(self, content_type: DocumentContentType | None = None, status: DocumentStatus | None = None) -> list[DocumentResponse]:
        with self._repository() as repository:
            return [DocumentResponse.model_validate(row) for row in repository.list_all(content_type, status)]

    def get_document(self, document_id: UUID) -> DocumentResponse:
        with self._repository() as repository:
            return DocumentResponse.model_validate(self._require(repository, document_id))

    def update_document(self, document_id: UUID, request: DocumentUpdateRequest) -> DocumentResponse:
        with self._repository() as repository:
            document = self._require(repository, document_id, write=True)
            if document.status == DocumentStatus.ARCHIVADO:
                raise DomainConflict("Un Document archivado no puede modificarse.")
            published = document.status == DocumentStatus.PUBLICADO
            if published and document.content_type == DocumentContentType.POST:
                raise DomainConflict("Un post publicado no puede modificarse.")
            if document.status not in {DocumentStatus.BORRADOR, DocumentStatus.PUBLICADO}:
                raise DomainConflict("El estado del Document no permite edición.")
            templates = repository.get_templates({document.template_id, request.template_id})
            current = self._template(templates, document.template_id, document.content_type)
            target = self._template(templates, request.template_id, document.content_type)
            if published and (not current.allow_published_edit or not target.allow_published_edit):
                raise DomainConflict("La Template no permite editar esta LANDING publicada.")
            self._validate(target, request.metadata_values, request.content, published=published)
            self._unique_slug(repository, request.slug, document_id)
            for key, value in request.model_dump(mode="python").items():
                setattr(document, key, value)
            document.updated_at = datetime.now(timezone.utc)
            repository.update(document)
            return DocumentResponse.model_validate(document)

    def publish_document(self, document_id: UUID) -> DocumentResponse:
        exported = None
        rendered = None
        try:
            with self._repository() as repository:
                document = self._require(repository, document_id, write=True)
                if document.status != DocumentStatus.BORRADOR:
                    raise DomainConflict("Solo puede publicarse un BORRADOR.")
                template = self._template(repository.get_templates({document.template_id}), document.template_id, document.content_type)
                self._validate(template, document.metadata_values or {}, document.content, published=True)
                if not document.title.strip():
                    raise BusinessRuleViolation("El título no puede estar vacío al publicar.")
                now = datetime.now(timezone.utc)
                if document.content_type == DocumentContentType.POST:
                    repository.lock_quarto_publication()
                    try:
                        exported = self._quarto_exporter.export_post(
                            slug=document.slug, title=document.title, metadata_values=document.metadata_values or {},
                            content=document.content, published_at=now,
                        )
                    except QuartoCollisionError:
                        raise DomainConflict("Ya existe contenido Quarto con ese slug.") from None
                    except QuartoExportError:
                        raise QuartoExportUnavailable("No fue posible exportar el contenido a Quarto.") from None
                    try:
                        rendered = self._quarto_render_service.render_site(document.slug)
                    except QuartoRenderError:
                        raise QuartoRenderUnavailable("No fue posible generar el sitio Quarto.") from None
                document.status = DocumentStatus.PUBLICADO
                document.published_at = now
                document.updated_at = now
                repository.update(document)
                response = DocumentResponse.model_validate(document)
                if rendered is not None:
                    logger.info("db_commit_started")
        except Exception:
            if exported is not None:
                logger.warning("compensation_started")
            compensation_failed = False
            if rendered is not None:
                try:
                    rendered.restore()
                except QuartoRenderError:
                    compensation_failed = True
            if exported is not None and exported.created:
                try:
                    self._quarto_exporter.remove_export(exported)
                except QuartoExportError:
                    compensation_failed = True
            if compensation_failed:
                raise QuartoRenderUnavailable("No fue posible compensar la publicación Quarto.") from None
            raise
        if rendered is not None:
            rendered.finalize()
        return response

    def archive_document(self, document_id: UUID) -> DocumentResponse:
        with self._repository() as repository:
            document = self._require(repository, document_id, write=True)
            if document.status != DocumentStatus.PUBLICADO:
                raise DomainConflict("Solo puede archivarse un Document PUBLICADO.")
            document.status = DocumentStatus.ARCHIVADO
            document.updated_at = datetime.now(timezone.utc)
            repository.update(document)
            return DocumentResponse.model_validate(document)

    def delete_document(self, document_id: UUID) -> None:
        with self._repository() as repository:
            document = self._require(repository, document_id, write=True)
            if document.status != DocumentStatus.BORRADOR:
                raise DomainConflict("Solo puede eliminarse un BORRADOR.")
            repository.delete(document)
