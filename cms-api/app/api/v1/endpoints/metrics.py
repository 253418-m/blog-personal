"""Router reservado para métricas; sin integración analítica."""

from fastapi import APIRouter


router = APIRouter(prefix="/documents", tags=["metrics"])

# TODO(CONTRACT_PENDING): precisar MetricSnapshot y los errores del proveedor.
