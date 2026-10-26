"""CRUD simplificado, invariantes y transacciones; independiente de FastAPI."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.core.exceptions import BusinessRuleViolation, DomainConflict, DomainError, ResourceNotFound
from app.domain.enums import TemplateTargetType
from app.infrastructure.database.models import TemplateModel
from app.infrastructure.database.template_repository import SQLAlchemyTemplateRepository
from app.repositories.interfaces import TemplateRepository
from app.schemas.template import TemplateCreateRequest, TemplateResponse, TemplateUpdateRequest


class TemplateStorageUnavailable(DomainError):
    """Fallo operativo sin detalles de SQL ni parámetros."""


class TemplateService:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def _repository(self, *, write: bool = False) -> Iterator[TemplateRepository]:
        try:
            with self._session_factory() as session, session.begin():
                repository = SQLAlchemyTemplateRepository(session)
                if write:
                    repository.lock_catalog()
                yield repository
        except IntegrityError as error:
            state = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if state == "23505" and constraint == "uq_templates_name":
                raise DomainConflict("Ya existe una Template con ese name.") from None
            if state in {"23001", "23503"} and constraint == "fk_documents_template_id_templates":
                raise DomainConflict("La Template está siendo utilizada por documentos.") from None
            raise TemplateStorageUnavailable("Servicio de Templates no disponible.") from None
        except SQLAlchemyError:
            raise TemplateStorageUnavailable("Servicio de Templates no disponible.") from None

    @staticmethod
    def _require(repository: TemplateRepository, template_id: UUID) -> TemplateModel:
        template = repository.get_by_id(template_id)
        if template is None:
            raise ResourceNotFound("Template no encontrada.")
        return template

    @staticmethod
    def _check_name(repository: TemplateRepository, name: str, template_id: UUID | None = None) -> None:
        existing = repository.get_by_name(name)
        if existing is not None and existing.template_id != template_id:
            raise DomainConflict("Ya existe una Template con ese name.")

    @staticmethod
    def _clear_previous_default(repository: TemplateRepository, template_id: UUID) -> None:
        previous = repository.get_default()
        if previous is not None and previous.template_id != template_id:
            previous.is_default = False
            repository.update(previous)

    def create_template(self, request: TemplateCreateRequest) -> TemplateResponse:
        with self._repository(write=True) as repository:
            self._check_name(repository, request.name)
            if repository.count() == 0 and not request.is_default:
                raise BusinessRuleViolation("La primera Template debe ser default.")
            template = TemplateModel(
                template_id=uuid7(), created_at=datetime.now(timezone.utc),
                **request.model_dump(mode="json"),
            )
            if request.is_default:
                self._clear_previous_default(repository, template.template_id)
            repository.create(template)
            return TemplateResponse.model_validate(template)

    def list_templates(self, target_type: TemplateTargetType | None = None) -> list[TemplateResponse]:
        with self._repository() as repository:
            return [TemplateResponse.model_validate(row) for row in repository.list_all(target_type)]

    def update_template(self, template_id: UUID, request: TemplateUpdateRequest) -> TemplateResponse:
        with self._repository(write=True) as repository:
            template = self._require(repository, template_id)
            self._check_name(repository, request.name, template_id)
            if template.is_default and not request.is_default:
                raise BusinessRuleViolation("Debe permanecer exactamente una Template default.")
            if request.is_default:
                self._clear_previous_default(repository, template_id)
            for field, value in request.model_dump(mode="json").items():
                setattr(template, field, value)
            repository.update(template)
            return TemplateResponse.model_validate(template)

    def delete_template(self, template_id: UUID) -> UUID:
        with self._repository(write=True) as repository:
            template = self._require(repository, template_id)
            if repository.count() == 1:
                raise DomainConflict("No se puede eliminar la última Template.")
            if repository.count_documents_using_template(template_id):
                raise DomainConflict("La Template está siendo utilizada por documentos.")
            if template.is_default:
                replacement = next(row for row in repository.list_all() if row.template_id != template_id)
                template.is_default = False
                repository.update(template)
                replacement.is_default = True
                repository.update(replacement)
            repository.delete(template)
            return template_id
