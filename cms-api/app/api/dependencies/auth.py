"""Bearer JWT para /auth/me; no cambia el estado de los demás routers."""

from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.jwt import InvalidAccessToken, decode_access_token
from app.infrastructure.database.admin_user_repository import SQLAlchemyAdminUserRepository
from app.infrastructure.database.models.admin_user import AdminUserModel
from app.infrastructure.database.session import SessionLocal, get_session
from app.services.auth_service import AuthService


bearer = HTTPBearer(auto_error=False, scheme_name="AdminBearer", bearerFormat="JWT")


def get_auth_service() -> AuthService:
    return AuthService(SessionLocal)


def _invalid_token() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="No se pudieron validar las credenciales.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminUserModel:
    if credentials is None:
        raise _invalid_token()
    try:
        user_id = decode_access_token(credentials.credentials, settings=settings)
    except InvalidAccessToken:
        raise _invalid_token() from None
    try:
        admin = SQLAlchemyAdminUserRepository(session).get_by_id(user_id)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Servicio de autenticación no disponible.") from None
    if admin is None:
        raise _invalid_token()
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Cuenta inactiva.")
    return admin
