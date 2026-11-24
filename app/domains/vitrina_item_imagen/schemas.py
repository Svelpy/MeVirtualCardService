from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase
from app.shared.schemas.examples import nested_examples, pick, response_examples
from app.shared.services.validators import (
    validator_https_url,
    validator_non_empty_text,
    validator_non_negative_integer,
)


_IDS = (
    "a87ff679-a2f3-4e1d-9c8b-7a6f5e4d3c2b",
    "a87ff679-a2f3-4e1d-9c8b-7a6f5e4d3c2c",
    "a87ff679-a2f3-4e1d-9c8b-7a6f5e4d3c2d",
)
_ID = _IDS[0]

# Una sola principal (orden 0) por item.
VITRINA_ITEM_IMAGEN_CREATE_EXAMPLES = [
    {
        "url": "https://res.cloudinary.com/demo/image/upload/v1/consulta.jpg",
        "alt": "Consultorio pediátrico",
        "orden": 0,
    },
    {
        "url": "https://res.cloudinary.com/demo/image/upload/v1/sala-espera.jpg",
        "alt": "Sala de espera con juegos",
        "orden": 1,
    },
    {
        "url": "https://res.cloudinary.com/demo/image/upload/v1/control-crecimiento.jpg",
        "alt": "Control de peso y talla",
        "orden": 2,
    },
]
VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLES = response_examples(
    VITRINA_ITEM_IMAGEN_CREATE_EXAMPLES, _IDS, item_id="e4da3b7f-bbce-4a4b-8f3c-2d1e0f9a8b7c"
)
VITRINA_ITEM_IMAGEN_PUBLIC_EXAMPLES = pick(VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLES, "id", "url", "alt", "orden")
VITRINA_ITEM_IMAGEN_NESTED_EXAMPLES = nested_examples(VITRINA_ITEM_IMAGEN_CREATE_EXAMPLES, _IDS)

VITRINA_ITEM_IMAGEN_CREATE_EXAMPLE = VITRINA_ITEM_IMAGEN_CREATE_EXAMPLES[0]
VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLE = VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLES[0]
VITRINA_ITEM_IMAGEN_PUBLIC_EXAMPLE = VITRINA_ITEM_IMAGEN_PUBLIC_EXAMPLES[0]

VITRINA_ITEM_IMAGEN_MAX = 3


def ensure_one_principal[T](items: Sequence[T]) -> None:
    """Una sola imagen principal (orden = 0) por item; lo usa la lista del item."""
    if sum(1 for item in items if getattr(item, "orden") == 0) > 1:
        raise ValueError("Solo puede haber una imagen principal (orden 0).")


# =================================
# Ronda 1: schemas planos
# =================================

class VitrinaItemImagenCreate(SchemaBase):
    """
    Hija embebida del item: item_id lo asigna el service. La URL es la que
    devolvió POST /imagenes/uploads; el service comprueba su origen.
    """

    url: str
    alt: str | None = Field(default=None, max_length=150)
    orden: int = Field(default=0, le=SMALLINT_MAX)  # 0 = principal

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: object) -> str:
        return validator_https_url(value)

    @field_validator("alt", mode="before")
    @classmethod
    def validate_alt(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_ITEM_IMAGEN_CREATE_EXAMPLE})


class VitrinaItemImagenResponse(SchemaBase):
    id: UUID
    item_id: UUID
    url: str
    alt: str | None
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLE})


class VitrinaItemImagenResponseAudit(AuditMixin, VitrinaItemImagenResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class VitrinaItemImagenPublic(SchemaBase):
    id: UUID
    url: str
    alt: str | None
    orden: int

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_ITEM_IMAGEN_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class VitrinaItemImagenNestedItem(VitrinaItemImagenCreate):
    """Elemento de la lista del padre: con id se actualiza, sin id se crea (AGENTS.md §20)."""

    id: UUID | None = None

    model_config = ConfigDict(json_schema_extra={"example": {**VITRINA_ITEM_IMAGEN_CREATE_EXAMPLE, "id": _ID}})
