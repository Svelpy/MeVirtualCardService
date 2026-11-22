from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.shared.enums import RedSocial
from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase
from app.shared.services.validators import (
    validator_boolean,
    validator_https_url,
    validator_non_empty_text,
    validator_non_negative_integer,
)


_ID = "c20ad4d7-6fe9-4759-8aa2-7f1e2d3c4b5a"

TARJETA_SOCIAL_CREATE_EXAMPLE = {
    "red": "instagram",
    "url": "https://www.instagram.com/dra.ana.perez",
    "username": "dra.ana.perez",
    "is_visible": True,
    "orden": 0,
}
TARJETA_SOCIAL_RESPONSE_EXAMPLE = {
    "id": _ID,
    "tarjeta_id": "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b",
    **TARJETA_SOCIAL_CREATE_EXAMPLE,
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
TARJETA_SOCIAL_PUBLIC_EXAMPLE = {
    "id": _ID,
    "red": "instagram",
    "url": "https://www.instagram.com/dra.ana.perez",
    "username": "dra.ana.perez",
}

# Una por red: el máximo de la lista es la cantidad de redes.
TARJETA_SOCIAL_MAX = len(RedSocial)


def ensure_unique_red[T](items: Sequence[T]) -> None:
    """Una cuenta por red en cada tarjeta; lo usa la lista del padre."""
    redes = [getattr(item, "red") for item in items]
    if len(redes) != len(set(redes)):
        raise ValueError("Solo puede haber una cuenta por red social.")


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaSocialCreate(SchemaBase):
    """Hija embebida de la tarjeta: tarjeta_id lo asigna el service."""

    red: RedSocial
    url: str
    username: str | None = Field(default=None, max_length=100)
    is_visible: bool = True
    orden: int = Field(default=0, le=SMALLINT_MAX)

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: object) -> str:
        return validator_https_url(value)

    @field_validator("username", mode="before")
    @classmethod
    def validate_username(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("is_visible", mode="before")
    @classmethod
    def validate_is_visible(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SOCIAL_CREATE_EXAMPLE})


class TarjetaSocialResponse(SchemaBase):
    id: UUID
    tarjeta_id: UUID
    red: RedSocial
    url: str
    username: str | None
    is_visible: bool
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SOCIAL_RESPONSE_EXAMPLE})


class TarjetaSocialResponseAudit(AuditMixin, TarjetaSocialResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_SOCIAL_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class TarjetaSocialPublic(SchemaBase):
    id: UUID
    red: RedSocial
    url: str
    username: str | None

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SOCIAL_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class TarjetaSocialNestedItem(TarjetaSocialCreate):
    """Elemento de la lista del padre: con id se actualiza, sin id se crea (AGENTS.md §20)."""

    id: UUID | None = None

    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_SOCIAL_CREATE_EXAMPLE, "id": _ID}})
