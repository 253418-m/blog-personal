"""Agregador central de routers de la versión 1."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, documents, metrics, preview, templates, workflow


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(templates.router)
api_router.include_router(documents.router)
api_router.include_router(workflow.router)
api_router.include_router(preview.router)
api_router.include_router(metrics.router)
