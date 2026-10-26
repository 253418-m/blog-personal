"""JWT de acceso firmado con HS256; los claims no contienen secretos."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import Settings, get_settings


class InvalidAccessToken(ValueError):
    """Token externo inválido, sin detalles de firma ni contenido."""


def create_access_token(user_id: UUID, *, settings: Settings | None = None) -> str:
    settings = settings if settings is not None else get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
            "type": "access",
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str, *, settings: Settings | None = None) -> UUID:
    settings = settings if settings is not None else get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp", "type"]},
        )
        if (
            claims["type"] != "access"
            or not isinstance(claims["sub"], str)
            or type(claims["iat"]) is not int
            or type(claims["exp"]) is not int
            or claims["exp"] <= claims["iat"]
        ):
            raise InvalidAccessToken("Token de acceso inválido.")
        return UUID(claims["sub"])
    except (InvalidTokenError, ValueError, TypeError, OverflowError):
        raise InvalidAccessToken("Token de acceso inválido.") from None
