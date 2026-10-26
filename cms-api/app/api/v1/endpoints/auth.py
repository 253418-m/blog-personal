"""Login JSON público y consulta del administrador autenticado mediante Bearer."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.api.dependencies.auth import get_auth_service, get_current_admin
from app.core.config import Settings, get_settings
from app.core.jwt import create_access_token
from app.infrastructure.database.models.admin_user import AdminUserModel
from app.schemas.auth import AuthErrorResponse, CurrentAdminResponse, LoginRequest, TokenResponse
from app.services.auth_service import AuthenticationUnavailable, AuthService, InvalidCredentials


class _SensitiveAuthRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original(request)
            except RequestValidationError:
                # El handler estándar incluye inputs: un body inválido podría
                # devolver la contraseña sin pasar por SecretStr.
                return JSONResponse(status_code=422, content={"detail": "Solicitud de autenticación inválida."})

        return handler


router = APIRouter(prefix="/auth", tags=["auth"], route_class=_SensitiveAuthRoute)


@router.post(
    "/login", response_model=TokenResponse,
    responses={401: {"model": AuthErrorResponse}, 422: {"model": AuthErrorResponse}, 503: {"model": AuthErrorResponse}},
)
def login(
    request: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        admin = service.authenticate(request.username, request.password.get_secret_value())
    except InvalidCredentials:
        raise HTTPException(
            status_code=401, detail="Credenciales inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except AuthenticationUnavailable:
        raise HTTPException(status_code=503, detail="Servicio de autenticación no disponible.") from None
    return TokenResponse(
        access_token=create_access_token(admin.user_id, settings=settings),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get(
    "/me", response_model=CurrentAdminResponse,
    responses={401: {"model": AuthErrorResponse}, 403: {"model": AuthErrorResponse}, 503: {"model": AuthErrorResponse}},
)
def me(admin: Annotated[AdminUserModel, Depends(get_current_admin)]) -> CurrentAdminResponse:
    return CurrentAdminResponse(user_id=admin.user_id, username=admin.username, is_active=admin.is_active)
