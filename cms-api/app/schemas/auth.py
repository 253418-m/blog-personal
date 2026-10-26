"""Contratos JSON de autenticación; nunca exponen el hash del administrador."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    username: str
    password: SecretStr = Field(repr=False, exclude=True)


class TokenResponse(BaseModel):
    access_token: str = Field(repr=False)
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0)


class CurrentAdminResponse(BaseModel):
    user_id: UUID
    username: str
    is_active: bool


class AuthErrorResponse(BaseModel):
    detail: str
