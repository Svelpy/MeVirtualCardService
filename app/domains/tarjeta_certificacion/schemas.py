from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase
from app.shared.schemas.examples import (
    TARJETA_ID_EXAMPLE,
    nested_examples,
    pick,
    response_examples,
)
from app.shared.services.validators import (
    validator_boolean,
    validator_date,
    validator_https_url,
    validator_non_empty_text,
    validator_non_negative_integer,
)


_IDS = (
    "9bf31c7f-f062-4a3a-8b2b-5c4d3e2f1a0b",
    "9bf31c7f-f062-4a3a-8b2b-5c4d3e2f1a0c",
    "9bf31c7f-f062-4a3a-8b2b-5c4d3e2f1a0d",
)
_ID = _IDS[0]

# no_expira true exige fecha_expiracion null: los ejemplos muestran certificaciones con vencimiento.
TARJETA_CERTIFICACION_CREATE_EXAMPLES = [
    {
        "nombre": "Certificación en Ecografía Básica",
        "entidad_emisora": "Sociedad Boliviana de Ecografía",
        "codigo_credencial": "SBE-2024-0153",
        "url_credencial": "https://sbe.example.org/credenciales/SBE-2024-0153",
        "fecha_emision": "2024-05-10",
        "fecha_expiracion": "2029-05-10",
        "no_expira": False,
        "descripcion": "Curso teórico-práctico de 120 horas.",
        "is_visible": True,
        "orden": 0,
    },
    {
        "nombre": "Reanimación Neonatal (NRP)",
        "entidad_emisora": "Sociedad Boliviana de Pediatría",
        "codigo_credencial": "SBP-NRP-2025-0412",
        "url_credencial": "https://sbp.example.org/credenciales/SBP-NRP-2025-0412",
        "fecha_emision": "2025-03-20",
        "fecha_expiracion": "2027-03-20",
        "no_expira": False,
        "descripcion": "Reanimación del recién nacido en sala de partos.",
        "is_visible": True,
        "orden": 1,
    },
    {
        "nombre": "Soporte Vital Pediátrico Avanzado (PALS)",
        "entidad_emisora": "Colegio Médico de La Paz",
        "codigo_credencial": "CMLP-PALS-2023-0098",
        "url_credencial": "https://colmedlp.example.org/credenciales/CMLP-PALS-2023-0098",
        "fecha_emision": "2023-09-05",
        "fecha_expiracion": "2025-09-05",
        "no_expira": False,
        "descripcion": "Manejo de emergencias pediátricas; vencida, oculta en la tarjeta.",
        "is_visible": False,
        "orden": 2,
    },
]
TARJETA_CERTIFICACION_RESPONSE_EXAMPLES = response_examples(
    TARJETA_CERTIFICACION_CREATE_EXAMPLES, _IDS, tarjeta_id=TARJETA_ID_EXAMPLE
)
TARJETA_CERTIFICACION_PUBLIC_EXAMPLES = pick(
    TARJETA_CERTIFICACION_RESPONSE_EXAMPLES,
    "id",
    "nombre",
    "entidad_emisora",
    "codigo_credencial",
    "url_credencial",
    "fecha_emision",
    "fecha_expiracion",
    "no_expira",
    "descripcion",
)
TARJETA_CERTIFICACION_NESTED_EXAMPLES = nested_examples(TARJETA_CERTIFICACION_CREATE_EXAMPLES, _IDS)

TARJETA_CERTIFICACION_CREATE_EXAMPLE = TARJETA_CERTIFICACION_CREATE_EXAMPLES[0]
TARJETA_CERTIFICACION_RESPONSE_EXAMPLE = TARJETA_CERTIFICACION_RESPONSE_EXAMPLES[0]
TARJETA_CERTIFICACION_PUBLIC_EXAMPLE = TARJETA_CERTIFICACION_PUBLIC_EXAMPLES[0]

TARJETA_CERTIFICACION_MAX = 10


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaCertificacionCreate(SchemaBase):
    """Hija embebida de la tarjeta: tarjeta_id lo asigna el service."""

    nombre: str = Field(max_length=200)
    entidad_emisora: str | None = Field(default=None, max_length=200)
    codigo_credencial: str | None = Field(default=None, max_length=150)
    url_credencial: str | None = None
    fecha_emision: date | None = None
    fecha_expiracion: date | None = None
    no_expira: bool = False
    descripcion: str | None = None
    is_visible: bool = True
    orden: int = Field(default=0, le=SMALLINT_MAX)

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        return validator_non_empty_text(value)

    @field_validator("entidad_emisora", "codigo_credencial", "descripcion", mode="before")
    @classmethod
    def validate_texto_opcional(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("url_credencial", mode="before")
    @classmethod
    def validate_url_credencial(cls, value: object) -> str | None:
        return None if value is None else validator_https_url(value)

    @field_validator("fecha_emision", "fecha_expiracion", mode="before")
    @classmethod
    def validate_fecha(cls, value: object) -> date | None:
        return None if value is None else validator_date(value)

    @field_validator("no_expira", "is_visible", mode="before")
    @classmethod
    def validate_booleano(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    @model_validator(mode="after")
    def validate_fechas(self) -> Self:
        if self.fecha_emision and self.fecha_expiracion and self.fecha_expiracion < self.fecha_emision:
            raise ValueError("La fecha de expiración no puede ser anterior a la de emisión.")
        if self.no_expira and self.fecha_expiracion is not None:
            raise ValueError("Una certificación que no expira no tiene fecha de expiración.")
        return self

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_CERTIFICACION_CREATE_EXAMPLE})


class TarjetaCertificacionResponse(SchemaBase):
    id: UUID
    tarjeta_id: UUID
    nombre: str
    entidad_emisora: str | None
    codigo_credencial: str | None
    url_credencial: str | None
    fecha_emision: date | None
    fecha_expiracion: date | None
    no_expira: bool
    descripcion: str | None
    is_visible: bool
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_CERTIFICACION_RESPONSE_EXAMPLE})


class TarjetaCertificacionResponseAudit(AuditMixin, TarjetaCertificacionResponse):
    model_config = ConfigDict(
        json_schema_extra={"example": {**TARJETA_CERTIFICACION_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}}
    )


class TarjetaCertificacionPublic(SchemaBase):
    id: UUID
    nombre: str
    entidad_emisora: str | None
    codigo_credencial: str | None
    url_credencial: str | None
    fecha_emision: date | None
    fecha_expiracion: date | None
    no_expira: bool
    descripcion: str | None

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_CERTIFICACION_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class TarjetaCertificacionNestedItem(TarjetaCertificacionCreate):
    """Elemento de la lista del padre: con id se actualiza, sin id se crea (AGENTS.md §20)."""

    id: UUID | None = None

    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_CERTIFICACION_CREATE_EXAMPLE, "id": _ID}})
