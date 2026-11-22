from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.shared.schemas.base import AUDIT_EXAMPLE, AuditMixin, SchemaBase, reject_null
from app.shared.services.validators import validator_boolean, validator_https_url, validator_non_empty_text


_CAMPOS_EXAMPLE = {
    "meta_title": "Dra. Ana Pérez · Pediatra en La Paz",
    "meta_description": "Consultas pediátricas, controles de crecimiento y vacunación en La Paz.",
    "og_image_url": "https://res.cloudinary.com/demo/image/upload/v1/og-ana-perez.jpg",
    "robots_index": True,
}
TARJETA_SEO_RESPONSE_EXAMPLE = {
    "id": "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b",
    **_CAMPOS_EXAMPLE,
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
TARJETA_SEO_PUBLIC_EXAMPLE = _CAMPOS_EXAMPLE


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaSeoCreate(SchemaBase):
    """
    Extensión 1:1: se crea junto con la tarjeta y con su mismo id. Un NULL se
    genera al publicar (título y descripción) o usa profile_url (imagen).
    """

    meta_title: str | None = Field(default=None, max_length=70)
    meta_description: str | None = Field(default=None, max_length=160)
    og_image_url: str | None = None
    robots_index: bool = True

    @field_validator("meta_title", "meta_description", mode="before")
    @classmethod
    def validate_texto_opcional(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("og_image_url", mode="before")
    @classmethod
    def validate_og_image_url(cls, value: object) -> str | None:
        return None if value is None else validator_https_url(value)

    @field_validator("robots_index", mode="before")
    @classmethod
    def validate_robots_index(cls, value: object) -> bool:
        return validator_boolean(value)

    model_config = ConfigDict(json_schema_extra={"example": _CAMPOS_EXAMPLE})


class TarjetaSeoUpdate(SchemaBase):
    meta_title: str | None = Field(default=None, max_length=70)
    meta_description: str | None = Field(default=None, max_length=160)
    og_image_url: str | None = Field(default=None)
    robots_index: bool = Field(default=None)

    @field_validator("meta_title", "meta_description", mode="before")
    @classmethod
    def validate_texto_opcional(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("og_image_url", mode="before")
    @classmethod
    def validate_og_image_url(cls, value: object) -> str | None:
        return None if value is None else validator_https_url(value)

    @field_validator("robots_index", mode="before")
    @classmethod
    def validate_robots_index(cls, value: object) -> bool:
        return validator_boolean(reject_null(value))

    model_config = ConfigDict(json_schema_extra={"example": _CAMPOS_EXAMPLE})


class TarjetaSeoResponse(SchemaBase):
    id: UUID
    meta_title: str | None
    meta_description: str | None
    og_image_url: str | None
    robots_index: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SEO_RESPONSE_EXAMPLE})


class TarjetaSeoResponseAudit(AuditMixin, TarjetaSeoResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_SEO_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class TarjetaSeoPublic(SchemaBase):
    meta_title: str | None
    meta_description: str | None
    og_image_url: str | None
    robots_index: bool

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SEO_PUBLIC_EXAMPLE})
