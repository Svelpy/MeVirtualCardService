from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase
from app.shared.schemas.examples import (
    TARJETA_ID_EXAMPLE,
    nested_examples,
    pick,
    response_examples,
)
from app.shared.services.validators import (
    validator_boolean,
    validator_non_empty_text,
    validator_non_negative_integer,
)


VITRINA_CATEGORIA_IDS = (
    "1f0e3dad-9990-4345-8b6a-5c4d3e2f1a09",
    "1f0e3dad-9990-4345-8b6a-5c4d3e2f1a10",
    "1f0e3dad-9990-4345-8b6a-5c4d3e2f1a11",
)
VITRINA_CATEGORIA_ID = VITRINA_CATEGORIA_IDS[0]

VITRINA_CATEGORIA_CREATE_EXAMPLES = [
    {"nombre": "Consultas", "is_visible": True, "orden": 0},
    {"nombre": "Paquetes", "is_visible": True, "orden": 1},
    {"nombre": "Talleres", "is_visible": False, "orden": 2},
]
VITRINA_CATEGORIA_RESPONSE_EXAMPLES = response_examples(
    VITRINA_CATEGORIA_CREATE_EXAMPLES, VITRINA_CATEGORIA_IDS, vitrina_id=TARJETA_ID_EXAMPLE
)
VITRINA_CATEGORIA_REF_EXAMPLES = pick(VITRINA_CATEGORIA_RESPONSE_EXAMPLES, "id", "nombre")
VITRINA_CATEGORIA_PUBLIC_EXAMPLES = VITRINA_CATEGORIA_REF_EXAMPLES
VITRINA_CATEGORIA_NESTED_EXAMPLES = nested_examples(VITRINA_CATEGORIA_CREATE_EXAMPLES, VITRINA_CATEGORIA_IDS)

VITRINA_CATEGORIA_CREATE_EXAMPLE = VITRINA_CATEGORIA_CREATE_EXAMPLES[0]
VITRINA_CATEGORIA_RESPONSE_EXAMPLE = VITRINA_CATEGORIA_RESPONSE_EXAMPLES[0]
VITRINA_CATEGORIA_REF_EXAMPLE = VITRINA_CATEGORIA_REF_EXAMPLES[0]
VITRINA_CATEGORIA_PUBLIC_EXAMPLE = VITRINA_CATEGORIA_PUBLIC_EXAMPLES[0]

VITRINA_CATEGORIA_MAX = 10


def ensure_unique_nombre[T](items: Sequence[T]) -> None:
    """Nombres únicos dentro de una vitrina; lo usa la lista de la vitrina."""
    nombres = [getattr(item, "nombre") for item in items]
    if len(nombres) != len(set(nombres)):
        raise ValueError("Hay categorías con el mismo nombre.")


# =================================
# Ronda 1: schemas planos
# =================================

class VitrinaCategoriaCreate(SchemaBase):
    """Hija embebida de la vitrina: vitrina_id lo asigna el service."""

    nombre: str = Field(max_length=60)
    is_visible: bool = True
    orden: int = Field(default=0, le=SMALLINT_MAX)

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        return validator_non_empty_text(value)

    @field_validator("is_visible", mode="before")
    @classmethod
    def validate_is_visible(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_CATEGORIA_CREATE_EXAMPLE})


class VitrinaCategoriaResponse(SchemaBase):
    id: UUID
    vitrina_id: UUID
    nombre: str
    is_visible: bool
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_CATEGORIA_RESPONSE_EXAMPLE})


class VitrinaCategoriaResponseAudit(AuditMixin, VitrinaCategoriaResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**VITRINA_CATEGORIA_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class VitrinaCategoriaRef(SchemaBase):
    id: UUID
    nombre: str

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_CATEGORIA_REF_EXAMPLE})


class VitrinaCategoriaPublic(SchemaBase):
    id: UUID
    nombre: str

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_CATEGORIA_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class VitrinaCategoriaNestedItem(VitrinaCategoriaCreate):
    """Elemento de la lista del padre: con id se actualiza, sin id se crea (AGENTS.md §20)."""

    id: UUID | None = None

    model_config = ConfigDict(json_schema_extra={"example": {**VITRINA_CATEGORIA_CREATE_EXAMPLE, "id": VITRINA_CATEGORIA_ID}})
