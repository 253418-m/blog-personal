"""Router reservado para live-preview, cuyo contrato requiere WebSocket."""

from fastapi import APIRouter


router = APIRouter(prefix="/documents", tags=["preview"])

# TODO(CONTRACT_PENDING): precisar el upgrade y la sesión antes de implementar.
