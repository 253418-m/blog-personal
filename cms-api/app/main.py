"""Punto de entrada ASGI de CMS Core API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings


app = FastAPI(
    title="CMS Core API",
    version="0.1.0",
    description=(
        "API interna para gestión del contenido editorial "
        "del Blog Dev y portafolio personal."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "auth", "description": "Autenticación administrativa JSON y Bearer JWT."},
        {"name": "templates", "description": "Plantillas editoriales."},
        {"name": "documents", "description": "Documentos administrados por el CMS."},
        {"name": "workflow", "description": "Flujo de revisión y publicación editorial."},
        {"name": "preview", "description": "Previsualización: implementación pendiente."},
        {"name": "metrics", "description": "Métricas: implementación pendiente."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_router, prefix="/api/v1")
