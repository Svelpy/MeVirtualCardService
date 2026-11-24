from datetime import datetime
from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.domains.plan.schemas import (
    PLAN_IDS,
    PLAN_REF_EXAMPLE,
    PLAN_REF_EXAMPLES,
    PLAN_RESPONSE_EXAMPLE,
    PlanRef,
    PlanResponse,
)
from app.domains.usuario.schemas import (
    USUARIO_REF_EXAMPLE,
    USUARIO_REF_EXAMPLES,
    USUARIO_RESPONSE_EXAMPLE,
    USUARIO_RESPONSE_EXAMPLES,
    UsuarioRef,
    UsuarioResponse,
)
from app.shared.enums import MetodoPago
from app.shared.schemas.base import AUDIT_EXAMPLE, AuditMixin, SchemaBase
from app.shared.services.validators import (
    validator_https_url,
    validator_non_empty_text,
    validator_non_negative_money,
)


PAGO_RESPONSE_EXAMPLE = {
    "id": "c4ca4238-a0b9-4382-8dcc-509a6f75849b",
    "user_id": "8f14e45f-ceea-467a-9575-6b3f0c1a2b3c",
    "plan_id": "7b1e9c40-0000-4000-8000-000000000002",
    # Un reverso: lleva reverses_id y su monto es negativo.
    "monto": "-80.00",
    "moneda": "USD",
    "metodo": "qr",
    "referencia_externa": "TRX-20260115-0001",
    "comprobante_url": "https://res.cloudinary.com/demo/image/upload/v1/comprobante.jpg",
    "periodo_inicio": "2026-01-15T14:30:00Z",
    "periodo_fin": "2027-01-15T14:30:00Z",
    "reverses_id": "c81e728d-9d4c-4f63-9f5a-1e2d3c4b5a69",
    "idempotency_key": "pago-8f14e45f-20260115-0001",
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-01-15T14:30:00Z",
}

# Un pago normal tiene reverses_id null: como un ejemplo no muestra campos vacíos,
# las variantes son reversos (monto negativo), cada uno de un pago distinto.
PAGO_RESPONSE_EXAMPLES = [
    PAGO_RESPONSE_EXAMPLE,
    {
        "id": "c4ca4238-a0b9-4382-8dcc-509a6f75849c",
        "user_id": USUARIO_RESPONSE_EXAMPLES[1]["id"],
        "plan_id": PLAN_IDS[2],
        "monto": "-200.00",
        "moneda": "USD",
        "metodo": "transferencia",
        "referencia_externa": "BNB-20260301-7781",
        "comprobante_url": "https://res.cloudinary.com/demo/image/upload/v1/comprobante-transferencia.jpg",
        "periodo_inicio": "2026-03-01T00:00:00Z",
        "periodo_fin": "2027-03-01T00:00:00Z",
        "reverses_id": "c81e728d-9d4c-4f63-9f5a-1e2d3c4b5a70",
        "idempotency_key": "pago-8f14e45f-20260301-0002",
        "created_at": "2026-03-02T10:15:00Z",
        "updated_at": "2026-03-02T10:15:00Z",
    },
    {
        "id": "c4ca4238-a0b9-4382-8dcc-509a6f75849d",
        "user_id": USUARIO_RESPONSE_EXAMPLES[2]["id"],
        "plan_id": PLAN_IDS[1],
        "monto": "-80.00",
        "moneda": "USD",
        "metodo": "efectivo",
        "referencia_externa": "RECIBO-000452",
        "comprobante_url": "https://res.cloudinary.com/demo/image/upload/v1/recibo-efectivo.jpg",
        "periodo_inicio": "2026-02-01T00:00:00Z",
        "periodo_fin": "2027-02-01T00:00:00Z",
        "reverses_id": "c81e728d-9d4c-4f63-9f5a-1e2d3c4b5a71",
        "idempotency_key": "pago-8f14e45f-20260201-0003",
        "created_at": "2026-02-03T16:40:00Z",
        "updated_at": "2026-02-03T16:40:00Z",
    },
]
_USUARIO_REFS = {usuario["id"]: usuario for usuario in USUARIO_REF_EXAMPLES}
_PLAN_REFS = {plan["id"]: plan for plan in PLAN_REF_EXAMPLES}


# =================================
# Ronda 1: schemas planos
# =================================

class PagoCreate(SchemaBase):
    """
    Registro de un pago por un admin (POST /pagos/registrar).

    monto es opcional: sin él se cobra el precio del plan; con él se registra
    otro importe, como una oferta de feria, sin tocar el precio oficial. Nunca
    supera el precio del plan (lo valida el service). La moneda y el periodo los
    calcula el service a partir del plan y del vencimiento actual del usuario.
    """

    user_id: UUID
    plan_id: UUID
    monto: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    metodo: MetodoPago
    referencia_externa: str | None = Field(default=None, max_length=100)
    comprobante_url: str | None = None
    # Un reintento con la misma clave no registra el pago dos veces.
    idempotency_key: str = Field(max_length=64)

    @field_validator("monto", mode="before")
    @classmethod
    def validate_monto(cls, value: object) -> Decimal | None:
        return None if value is None else validator_non_negative_money(value)

    @field_validator("referencia_externa", mode="before")
    @classmethod
    def validate_referencia_externa(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("comprobante_url", mode="before")
    @classmethod
    def validate_comprobante_url(cls, value: object) -> str | None:
        return None if value is None else validator_https_url(value)

    @field_validator("idempotency_key", mode="before")
    @classmethod
    def validate_idempotency_key(cls, value: object) -> str:
        return validator_non_empty_text(value)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "8f14e45f-ceea-467a-9575-6b3f0c1a2b3c",
                "plan_id": "7b1e9c40-0000-4000-8000-000000000002",
                "monto": "60.00",
                "metodo": "qr",
                "referencia_externa": "TRX-20260115-0001",
                "comprobante_url": "https://res.cloudinary.com/demo/image/upload/v1/comprobante.jpg",
                "idempotency_key": "pago-8f14e45f-20260115-0001",
            }
        }
    )


class PagoResponse(SchemaBase):
    id: UUID
    user_id: UUID
    plan_id: UUID
    monto: Decimal
    moneda: str
    metodo: MetodoPago
    referencia_externa: str | None
    comprobante_url: str | None
    periodo_inicio: datetime
    periodo_fin: datetime
    reverses_id: UUID | None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": PAGO_RESPONSE_EXAMPLE})


class PagoResponseAudit(AuditMixin, PagoResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**PAGO_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class PagoResponseItemList(PagoResponse):
    user: UsuarioRef
    plan: PlanRef

    # Ejemplo de GET /pagos.
    PAGE_EXAMPLES: ClassVar[list[dict]] = [
        {**pago, "user": _USUARIO_REFS[pago["user_id"]], "plan": _PLAN_REFS[pago["plan_id"]]}
        for pago in PAGO_RESPONSE_EXAMPLES
    ]

    model_config = ConfigDict(
        json_schema_extra={"example": {**PAGO_RESPONSE_EXAMPLE, "user": USUARIO_REF_EXAMPLE, "plan": PLAN_REF_EXAMPLE}}
    )


class PagoResponseDetail(PagoResponse):
    user: UsuarioResponse
    plan: PlanResponse

    model_config = ConfigDict(
        json_schema_extra={
            "example": {**PAGO_RESPONSE_EXAMPLE, "user": USUARIO_RESPONSE_EXAMPLE, "plan": PLAN_RESPONSE_EXAMPLE}
        }
    )
