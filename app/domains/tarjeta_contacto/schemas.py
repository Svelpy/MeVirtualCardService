from collections.abc import Sequence
from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, ValidationInfo, field_validator, model_validator, validate_email

from app.shared.enums import TipoContacto
from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase
from app.shared.schemas.examples import (
    TARJETA_ID_EXAMPLE,
    nested_examples,
    pick,
    response_examples,
)
from app.shared.services.validators import (
    validator_boolean,
    validator_email,
    validator_https_url,
    validator_non_empty_text,
    validator_non_negative_integer,
    validator_phone,
)


_IDS = (
    "c51ce410-c124-4a10-8e4d-2b3a4c5d6e7f",
    "aab32389-22bc-4c56-8a7e-3f2e1d0c9b01",
    "9bf31c7f-f062-4a3a-8b2b-5c4d3e2f1a02",
)
_ID = _IDS[0]

TARJETA_CONTACTO_CREATE_EXAMPLES = [
    {
        "tipo": "phone",
        "valor": "+59170000001",
        "etiqueta": "Celular",
        "is_wpp": True,
        "is_primary": True,
        "is_visible": True,
        "orden": 0,
    },
    {
        "tipo": "email",
        "valor": "consultas@draanaperez.com",
        "etiqueta": "Correo de consultas",
        "is_wpp": False,
        "is_primary": True,
        "is_visible": True,
        "orden": 1,
    },
    {
        "tipo": "website",
        "valor": "https://draanaperez.com",
        "etiqueta": "Sitio web",
        "is_wpp": False,
        "is_primary": False,
        "is_visible": False,
        "orden": 2,
    },
]
TARJETA_CONTACTO_RESPONSE_EXAMPLES = response_examples(
    TARJETA_CONTACTO_CREATE_EXAMPLES, _IDS, tarjeta_id=TARJETA_ID_EXAMPLE
)
TARJETA_CONTACTO_PUBLIC_EXAMPLES = pick(
    TARJETA_CONTACTO_RESPONSE_EXAMPLES, "id", "tipo", "valor", "etiqueta", "is_wpp", "is_primary"
)
TARJETA_CONTACTO_NESTED_EXAMPLES = nested_examples(TARJETA_CONTACTO_CREATE_EXAMPLES, _IDS)

TARJETA_CONTACTO_CREATE_EXAMPLE = TARJETA_CONTACTO_CREATE_EXAMPLES[0]
TARJETA_CONTACTO_RESPONSE_EXAMPLE = TARJETA_CONTACTO_RESPONSE_EXAMPLES[0]
TARJETA_CONTACTO_PUBLIC_EXAMPLE = TARJETA_CONTACTO_PUBLIC_EXAMPLES[0]

TARJETA_CONTACTO_MAX = 10


def ensure_one_primary_per_tipo[T](items: Sequence[T]) -> None:
    """Un solo contacto principal por tipo en cada tarjeta; lo usa la lista del padre."""
    tipos = [getattr(item, "tipo") for item in items if getattr(item, "is_primary")]
    if len(tipos) != len(set(tipos)):
        raise ValueError("Solo puede haber un contacto principal por tipo.")


def _validate_valor(tipo: TipoContacto | None, value: object) -> str:
    """El formato del valor depende del tipo: teléfono, email o sitio web."""
    if tipo is TipoContacto.PHONE:
        return validator_phone(value)
    if tipo is TipoContacto.EMAIL:
        email = validator_email(value)
        try:
            validate_email(email)
        except Exception as error:
            raise ValueError("El email no tiene un formato válido.") from error
        return email
    if tipo is TipoContacto.WEBSITE:
        return validator_https_url(value)
    # Sin un tipo válido, Pydantic ya informa el error del tipo.
    return validator_non_empty_text(value)


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaContactoCreate(SchemaBase):
    """Hija embebida de la tarjeta: tarjeta_id lo asigna el service."""

    tipo: TipoContacto
    valor: str = Field(max_length=255)
    etiqueta: str | None = Field(default=None, max_length=60)
    is_wpp: bool = False
    is_primary: bool = False
    is_visible: bool = True
    orden: int = Field(default=0, le=SMALLINT_MAX)

    @field_validator("valor", mode="before")
    @classmethod
    def validate_valor(cls, value: object, info: ValidationInfo) -> str:
        return _validate_valor(info.data.get("tipo"), value)

    @field_validator("etiqueta", mode="before")
    @classmethod
    def validate_etiqueta(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("is_wpp", "is_primary", "is_visible", mode="before")
    @classmethod
    def validate_booleano(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    @model_validator(mode="after")
    def validate_wpp(self) -> Self:
        if self.is_wpp and self.tipo is not TipoContacto.PHONE:
            raise ValueError("Solo un teléfono puede marcarse como WhatsApp.")
        return self

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_CONTACTO_CREATE_EXAMPLE})


class TarjetaContactoResponse(SchemaBase):
    id: UUID
    tarjeta_id: UUID
    tipo: TipoContacto
    valor: str
    etiqueta: str | None
    is_wpp: bool
    is_primary: bool
    is_visible: bool
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_CONTACTO_RESPONSE_EXAMPLE})


class TarjetaContactoResponseAudit(AuditMixin, TarjetaContactoResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_CONTACTO_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class TarjetaContactoPublic(SchemaBase):
    id: UUID
    tipo: TipoContacto
    valor: str
    etiqueta: str | None
    is_wpp: bool
    is_primary: bool

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_CONTACTO_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class TarjetaContactoNestedItem(TarjetaContactoCreate):
    """Elemento de la lista del padre: con id se actualiza, sin id se crea (AGENTS.md §20)."""

    id: UUID | None = None

    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_CONTACTO_CREATE_EXAMPLE, "id": _ID}})
