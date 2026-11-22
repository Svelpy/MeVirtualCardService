from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.shared.enums import ClaveSeccion
from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase
from app.shared.services.validators import (
    validator_boolean,
    validator_non_empty_text,
    validator_non_negative_integer,
)


_ID = "45c48cce-2e2d-4fbd-aa1a-9b8c7d6e5f4a"

TARJETA_SECCION_CREATE_EXAMPLE = {"titulo": "Sobre mí", "is_visible": True, "orden": 0}
TARJETA_SECCION_RESPONSE_EXAMPLE = {
    "id": _ID,
    "tarjeta_id": "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b",
    "clave": "acerca",
    **TARJETA_SECCION_CREATE_EXAMPLE,
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
TARJETA_SECCION_PUBLIC_EXAMPLE = {"clave": "acerca", "titulo": "Sobre mí"}

# Las 8 secciones fijas, una por ClaveSeccion.
TARJETA_SECCION_COUNT = len(ClaveSeccion)


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaSeccionCreate(SchemaBase):
    """
    Hija embebida fija: el service crea las 8 junto con la tarjeta (una por
    clave) y por la API solo se actualizan. La clave no se edita.
    """

    titulo: str | None = Field(default=None, max_length=80)
    is_visible: bool = True
    orden: int = Field(default=0, le=SMALLINT_MAX)

    @field_validator("titulo", mode="before")
    @classmethod
    def validate_titulo(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("is_visible", mode="before")
    @classmethod
    def validate_is_visible(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SECCION_CREATE_EXAMPLE})


class TarjetaSeccionResponse(SchemaBase):
    id: UUID
    tarjeta_id: UUID
    clave: ClaveSeccion
    titulo: str | None
    is_visible: bool
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SECCION_RESPONSE_EXAMPLE})


class TarjetaSeccionResponseAudit(AuditMixin, TarjetaSeccionResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_SECCION_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class TarjetaSeccionPublic(SchemaBase):
    """Solo las secciones visibles, en su orden."""

    clave: ClaveSeccion
    titulo: str | None

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SECCION_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class TarjetaSeccionNestedItem(TarjetaSeccionCreate):
    """Elemento de la lista fija de la tarjeta: el id es obligatorio, porque las 8 secciones ya existen y por la API solo se actualizan."""

    id: UUID

    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_SECCION_CREATE_EXAMPLE, "id": _ID}})
