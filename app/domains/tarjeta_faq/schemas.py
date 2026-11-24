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


_IDS = (
    "6512bd43-d9ca-4a6e-8b0b-1f2e3d4c5b6a",
    "6512bd43-d9ca-4a6e-8b0b-1f2e3d4c5b6b",
    "6512bd43-d9ca-4a6e-8b0b-1f2e3d4c5b6c",
)
_ID = _IDS[0]

TARJETA_FAQ_CREATE_EXAMPLES = [
    {
        "pregunta": "¿Atiende fines de semana?",
        "respuesta": "Sí, los sábados de 9:00 a 13:00.",
        "is_visible": True,
        "orden": 0,
    },
    {
        "pregunta": "¿Trabaja con seguros de salud?",
        "respuesta": "Sí, con la Caja Nacional de Salud y los principales seguros privados.",
        "is_visible": True,
        "orden": 1,
    },
    {
        "pregunta": "¿Hace consultas a domicilio?",
        "respuesta": "Solo en la zona sur de La Paz, con cita previa.",
        "is_visible": False,
        "orden": 2,
    },
]
TARJETA_FAQ_RESPONSE_EXAMPLES = response_examples(TARJETA_FAQ_CREATE_EXAMPLES, _IDS, tarjeta_id=TARJETA_ID_EXAMPLE)
TARJETA_FAQ_PUBLIC_EXAMPLES = pick(TARJETA_FAQ_RESPONSE_EXAMPLES, "id", "pregunta", "respuesta")
TARJETA_FAQ_NESTED_EXAMPLES = nested_examples(TARJETA_FAQ_CREATE_EXAMPLES, _IDS)

TARJETA_FAQ_CREATE_EXAMPLE = TARJETA_FAQ_CREATE_EXAMPLES[0]
TARJETA_FAQ_RESPONSE_EXAMPLE = TARJETA_FAQ_RESPONSE_EXAMPLES[0]
TARJETA_FAQ_PUBLIC_EXAMPLE = TARJETA_FAQ_PUBLIC_EXAMPLES[0]

TARJETA_FAQ_MAX = 30


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaFaqCreate(SchemaBase):
    """Hija embebida de la tarjeta: tarjeta_id lo asigna el service."""

    pregunta: str = Field(max_length=300)
    respuesta: str
    is_visible: bool = True
    orden: int = Field(default=0, le=SMALLINT_MAX)

    @field_validator("pregunta", "respuesta", mode="before")
    @classmethod
    def validate_texto(cls, value: object) -> str:
        return validator_non_empty_text(value)

    @field_validator("is_visible", mode="before")
    @classmethod
    def validate_is_visible(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_FAQ_CREATE_EXAMPLE})


class TarjetaFaqResponse(SchemaBase):
    id: UUID
    tarjeta_id: UUID
    pregunta: str
    respuesta: str
    is_visible: bool
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_FAQ_RESPONSE_EXAMPLE})


class TarjetaFaqResponseAudit(AuditMixin, TarjetaFaqResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_FAQ_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class TarjetaFaqPublic(SchemaBase):
    id: UUID
    pregunta: str
    respuesta: str

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_FAQ_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class TarjetaFaqNestedItem(TarjetaFaqCreate):
    """Elemento de la lista del padre: con id se actualiza, sin id se crea (AGENTS.md §20)."""

    id: UUID | None = None

    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_FAQ_CREATE_EXAMPLE, "id": _ID}})
