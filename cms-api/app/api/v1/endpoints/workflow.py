"""Router de flujo editorial; sin transiciones implementadas todavía."""

from fastapi import APIRouter


router = APIRouter(prefix="/documents", tags=["workflow"])

# TODO: implementar submit-review, review-report, publish y archive por contrato.
