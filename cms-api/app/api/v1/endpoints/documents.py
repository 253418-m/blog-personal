"""Router de documentos; casos de uso pendientes de implementación."""

from fastapi import APIRouter


router = APIRouter(prefix="/documents", tags=["documents"])

# TODO(CONTRACT_PENDING): completar schemas antes de registrar POST/GET/PUT/DELETE.
# PATCH no tiene contrato y no se registra.
