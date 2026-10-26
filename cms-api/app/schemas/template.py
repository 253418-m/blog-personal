"""Contrato simplificado de Templates del Blog Personal."""

from typing import Annotated
from datetime import datetime, timezone
from uuid import UUID

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, JsonValue,
    StrictBool, StringConstraints, field_validator,
)

from app.domain.enums import MetadataExpectedType, TemplateTargetType


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MetadataContractItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_key: NonEmptyString
    expected_type: MetadataExpectedType
    is_required: StrictBool


class TemplateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonEmptyString
    is_default: StrictBool
    metadata_contract: list[MetadataContractItem] = Field(min_length=1)
    layout_structure: dict[str, JsonValue]

    @field_validator("metadata_contract")
    @classmethod
    def unique_field_keys(cls, items: list[MetadataContractItem]) -> list[MetadataContractItem]:
        keys = [item.field_key for item in items]
        if len(set(keys)) != len(keys):
            raise ValueError("metadata_contract no permite field_key duplicados.")
        return items


class TemplateCreateRequest(TemplateUpdateRequest):
    target_type: TemplateTargetType
    allow_published_edit: StrictBool


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    template_id: UUID
    name: str
    target_type: TemplateTargetType
    is_default: bool
    allow_published_edit: bool
    metadata_contract: list[MetadataContractItem]
    layout_structure: dict[str, JsonValue]
    created_at: AwareDatetime

    @field_validator("created_at")
    @classmethod
    def utc_created_at(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class TemplateListResponse(BaseModel):
    items: list[TemplateResponse]


class TemplateDeleteResponse(BaseModel):
    deleted_template_id: UUID
