"""CRUD administrativo de Templates; las reglas pertenecen al servicio."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.routing import APIRoute

from app.api.dependencies.auth import get_current_admin
from app.core.exceptions import BusinessRuleViolation, DomainConflict, ResourceNotFound
from app.domain.enums import TemplateTargetType
from app.infrastructure.database.session import SessionLocal
from app.schemas.template import (
    TemplateCreateRequest, TemplateDeleteResponse, TemplateListResponse,
    TemplateResponse, TemplateUpdateRequest,
)
from app.services.template_service import TemplateService, TemplateStorageUnavailable


class _TemplateRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original(request)
            except (ResourceNotFound, DomainConflict, BusinessRuleViolation, TemplateStorageUnavailable) as error:
                status = {
                    ResourceNotFound: 404, DomainConflict: 409,
                    BusinessRuleViolation: 422, TemplateStorageUnavailable: 503,
                }[type(error)]
                raise HTTPException(status_code=status, detail=str(error)) from None

        return handler


def get_template_service() -> TemplateService:
    return TemplateService(SessionLocal)


router = APIRouter(
    prefix="/templates", tags=["templates"], route_class=_TemplateRoute,
    dependencies=[Depends(get_current_admin)],
    responses={401: {"description": "Bearer ausente o inválido"},
               403: {"description": "Cuenta inactiva"},
               503: {"description": "Persistencia no disponible"}},
)
Service = Annotated[TemplateService, Depends(get_template_service)]


@router.post("", status_code=201, response_model=TemplateResponse,
             responses={409: {"description": "Name duplicado"}})
def create_template(request: TemplateCreateRequest, service: Service) -> TemplateResponse:
    return service.create_template(request)


@router.get("", response_model=TemplateListResponse)
def list_templates(service: Service, target_type: Annotated[TemplateTargetType | None, Query()] = None) -> TemplateListResponse:
    return TemplateListResponse(items=service.list_templates(target_type))


@router.put("/{template_id}", response_model=TemplateResponse,
            responses={404: {"description": "Template no encontrada"},
                       409: {"description": "Name duplicado"}})
def update_template(template_id: UUID, request: TemplateUpdateRequest, service: Service) -> TemplateResponse:
    return service.update_template(template_id, request)


@router.delete("/{template_id}", response_model=TemplateDeleteResponse,
               responses={404: {"description": "Template no encontrada"},
                          409: {"description": "Última Template o utilizada por documentos"}})
def delete_template(template_id: UUID, service: Service) -> TemplateDeleteResponse:
    return TemplateDeleteResponse(deleted_template_id=service.delete_template(template_id))
