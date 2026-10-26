"""Acceso SQLAlchemy; el servicio es dueño de la transacción."""

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.domain.enums import TemplateTargetType
from app.infrastructure.database.models import DocumentModel, TemplateModel


class SQLAlchemyTemplateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_catalog(self) -> None:
        # También protege el catálogo vacío. Las lecturas normales siguen libres;
        # las escrituras se serializan hasta commit/rollback, sin tablas nuevas.
        self._session.execute(text("LOCK TABLE templates IN SHARE ROW EXCLUSIVE MODE"))

    def get_by_id(self, template_id: UUID) -> TemplateModel | None:
        return self._session.get(TemplateModel, template_id)

    def get_by_name(self, name: str) -> TemplateModel | None:
        return self._session.scalar(select(TemplateModel).where(TemplateModel.name == name))

    def count(self) -> int:
        return self._session.scalar(select(func.count()).select_from(TemplateModel))

    def get_default(self) -> TemplateModel | None:
        return self._session.scalar(select(TemplateModel).where(TemplateModel.is_default.is_(True)))

    def list_all(self, target_type: TemplateTargetType | None = None) -> list[TemplateModel]:
        statement = select(TemplateModel).order_by(TemplateModel.created_at, TemplateModel.template_id)
        if target_type is not None:
            statement = statement.where(TemplateModel.target_type == target_type.value)
        return list(self._session.scalars(statement))

    def create(self, template: TemplateModel) -> None:
        self._session.add(template)
        self._session.flush()

    def update(self, template: TemplateModel) -> None:
        self._session.add(template)
        self._session.flush()

    def delete(self, template: TemplateModel) -> None:
        self._session.delete(template)
        self._session.flush()

    def count_documents_using_template(self, template_id: UUID) -> int:
        return self._session.scalar(
            select(func.count()).select_from(DocumentModel)
            .where(DocumentModel.template_id == template_id)
        )
