"""Requests y respuestas del Document simplificado; sin renderizar contenido."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, JsonValue, StringConstraints, field_validator

from app.domain.enums import DocumentContentType, DocumentStatus


class DocumentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    slug: Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
    template_id: UUID
    metadata_values: dict[str, JsonValue]
    content: str


class DocumentCreateRequest(DocumentUpdateRequest):
    content_type: DocumentContentType


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    title: str
    slug: str
    content_type: DocumentContentType
    status: DocumentStatus
    template_id: UUID
    metadata_values: dict[str, JsonValue]
    content: str
    created_at: AwareDatetime
    updated_at: AwareDatetime
    published_at: AwareDatetime | None

    @field_validator("created_at", "updated_at", "published_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(timezone.utc) if value is not None else None


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
