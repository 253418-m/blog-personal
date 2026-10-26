"""API administrativa de Documents con export y render POST al publicar."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.routing import APIRoute

from app.api.dependencies.auth import get_current_admin
from app.core.config import get_settings
from app.core.exceptions import BusinessRuleViolation, DomainConflict, ResourceNotFound
from app.domain.enums import DocumentContentType, DocumentStatus
from app.infrastructure.database.session import SessionLocal
from app.schemas.document import DocumentCreateRequest, DocumentListResponse, DocumentResponse, DocumentUpdateRequest
from app.services.document_service import (DocumentService, DocumentStorageUnavailable,
                                           QuartoExportUnavailable, QuartoRenderUnavailable)
from app.services.quarto_export import FileSystemQuartoExporter
from app.services.quarto_render import QuartoRenderService, SubprocessQuartoRenderer


class _DocumentRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original(request)
            except (ResourceNotFound, DomainConflict, BusinessRuleViolation, DocumentStorageUnavailable,
                    QuartoExportUnavailable, QuartoRenderUnavailable) as error:
                status = {ResourceNotFound: 404, DomainConflict: 409,
                          BusinessRuleViolation: 422, DocumentStorageUnavailable: 503,
                          QuartoExportUnavailable: 500, QuartoRenderUnavailable: 500}[type(error)]
                raise HTTPException(status_code=status, detail=str(error)) from None

        return handler


def get_document_service() -> DocumentService:
    settings = get_settings()
    root = settings.quarto_project_root
    renderer = SubprocessQuartoRenderer(root, settings.quarto_executable, settings.quarto_render_timeout_seconds)
    return DocumentService(SessionLocal, FileSystemQuartoExporter(root), QuartoRenderService(root, renderer))


router = APIRouter(
    prefix="/documents", tags=["documents"], route_class=_DocumentRoute,
    dependencies=[Depends(get_current_admin)],
    responses={401: {"description": "Bearer ausente o inválido"}, 403: {"description": "Cuenta inactiva"},
               404: {"description": "Document o Template no encontrado"},
               409: {"description": "Conflicto de slug o estado"},
               422: {"description": "Solicitud o metadatos inválidos"},
               500: {"description": "No fue posible exportar o generar el sitio Quarto"},
               503: {"description": "Persistencia no disponible"}},
)
Service = Annotated[DocumentService, Depends(get_document_service)]


@router.post("", status_code=201, response_model=DocumentResponse)
def create_document(request: DocumentCreateRequest, service: Service) -> DocumentResponse:
    return service.create_document(request)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    service: Service,
    content_type: Annotated[DocumentContentType | None, Query()] = None,
    status: Annotated[DocumentStatus | None, Query()] = None,
) -> DocumentListResponse:
    return DocumentListResponse(items=service.list_documents(content_type, status))


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID, service: Service) -> DocumentResponse:
    return service.get_document(document_id)


@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(document_id: UUID, request: DocumentUpdateRequest, service: Service) -> DocumentResponse:
    return service.update_document(document_id, request)


@router.post("/{document_id}/publish", response_model=DocumentResponse)
def publish_document(document_id: UUID, service: Service) -> DocumentResponse:
    return service.publish_document(document_id)


@router.post("/{document_id}/archive", response_model=DocumentResponse)
def archive_document(document_id: UUID, service: Service) -> DocumentResponse:
    return service.archive_document(document_id)


@router.delete("/{document_id}", status_code=204, response_class=Response)
def delete_document(document_id: UUID, service: Service) -> Response:
    service.delete_document(document_id)
    return Response(status_code=204)
