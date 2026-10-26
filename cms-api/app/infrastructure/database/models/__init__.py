"""Registro explícito de las entidades editoriales y administrativas."""

from app.infrastructure.database.models.admin_user import AdminUserModel
from app.infrastructure.database.models.canvas_block import CanvasBlockModel
from app.infrastructure.database.models.document import DocumentModel
from app.infrastructure.database.models.review_report import ReviewReportModel
from app.infrastructure.database.models.template import TemplateModel

__all__ = [
    "AdminUserModel",
    "TemplateModel",
    "DocumentModel",
    "CanvasBlockModel",
    "ReviewReportModel",
]
