from datetime import datetime
from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase, reject_null
from app.shared.services.validators import (
    validator_boolean,
    validator_currency_code,
    validator_non_empty_text,
    validator_non_negative_money,
    validator_positive_integer,
)


PLAN_PRO_ID = "7b1e9c40-0000-4000-8000-000000000002"

_UPDATE_EXAMPLE = {
    "nombre": "Pro",
    "precio": "80.00",
    "moneda": "USD",
    "duracion_dias": 365,
    "is_visible": True,
}
PLAN_RESPONSE_EXAMPLE = {
    "id": PLAN_PRO_ID,
    "codigo": "pro",
    **_UPDATE_EXAMPLE,
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
PLAN_REF_EXAMPLE = {"id": PLAN_PRO_ID, "nombre": "Pro"}

# Las 3 filas fijas, sembradas en la migración inicial.
PLAN_IDS = (
    "7b1e9c40-0000-4000-8000-000000000001",
    PLAN_PRO_ID,
    "7b1e9c40-0000-4000-8000-000000000003",
)
PLAN_RESPONSE_EXAMPLES = [
    {
        "id": PLAN_IDS[0],
        "codigo": "free",
        "nombre": "Free",
        "precio": "0.00",
        "moneda": "USD",
        "duracion_dias": 7,
        "is_visible": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    },
    PLAN_RESPONSE_EXAMPLE,
    {
        "id": PLAN_IDS[2],
        "codigo": "business",
        "nombre": "Business",
        "precio": "200.00",
        "moneda": "USD",
        "duracion_dias": 365,
        "is_visible": False,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-02-10T08:00:00Z",
    },
]
PLAN_REF_EXAMPLES = [{"id": plan["id"], "nombre": plan["nombre"]} for plan in PLAN_RESPONSE_EXAMPLES]


# =================================
# Ronda 1: schemas planos
# =================================

class PlanUpdate(SchemaBase):
    """Filas fijas: el admin edita todo menos el código."""

    nombre: str = Field(default=None, max_length=60)
    precio: Decimal = Field(default=None, max_digits=12, decimal_places=2)
    moneda: str = Field(default=None, min_length=3, max_length=3)
    duracion_dias: int = Field(default=None, le=SMALLINT_MAX)
    is_visible: bool = Field(default=None)

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        return validator_non_empty_text(reject_null(value))

    @field_validator("precio", mode="before")
    @classmethod
    def validate_precio(cls, value: object) -> Decimal:
        return validator_non_negative_money(reject_null(value))

    @field_validator("moneda", mode="before")
    @classmethod
    def validate_moneda(cls, value: object) -> str:
        return validator_currency_code(reject_null(value))

    @field_validator("duracion_dias", mode="before")
    @classmethod
    def validate_duracion_dias(cls, value: object) -> int:
        return validator_positive_integer(reject_null(value))

    @field_validator("is_visible", mode="before")
    @classmethod
    def validate_is_visible(cls, value: object) -> bool:
        return validator_boolean(reject_null(value))

    model_config = ConfigDict(json_schema_extra={"example": _UPDATE_EXAMPLE})


class PlanResponse(SchemaBase):
    id: UUID
    codigo: str
    nombre: str
    precio: Decimal
    moneda: str
    duracion_dias: int
    is_visible: bool
    created_at: datetime
    updated_at: datetime

    PAGE_EXAMPLES: ClassVar[list[dict]] = PLAN_RESPONSE_EXAMPLES  # ejemplo de GET /planes

    model_config = ConfigDict(json_schema_extra={"example": PLAN_RESPONSE_EXAMPLE})


class PlanResponseAudit(AuditMixin, PlanResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**PLAN_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class PlanRef(SchemaBase):
    id: UUID
    nombre: str

    model_config = ConfigDict(json_schema_extra={"example": PLAN_REF_EXAMPLE})


class PlanPublic(SchemaBase):
    """Página de precios: solo los planes con is_visible."""

    id: UUID
    codigo: str
    nombre: str
    precio: Decimal
    moneda: str
    duracion_dias: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": PLAN_PRO_ID,
                "codigo": "pro",
                "nombre": "Pro",
                "precio": "80.00",
                "moneda": "USD",
                "duracion_dias": 365,
            }
        }
    )
