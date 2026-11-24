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
    validator_non_empty_text,
    validator_non_negative_integer,
)


_IDS = (
    "aab32389-22bc-4c56-8a7e-3f2e1d0c9b8a",
    "aab32389-22bc-4c56-8a7e-3f2e1d0c9b8b",
    "aab32389-22bc-4c56-8a7e-3f2e1d0c9b8c",
)
_ID = _IDS[0]

# is_actual true exige fecha_fin null: los ejemplos muestran estudios terminados.
TARJETA_EDUCACION_CREATE_EXAMPLES = [
    {
        "institucion": "Universidad Mayor de San Andrés",
        "titulo": "Licenciatura en Medicina",
        "area_estudio": "Medicina",
        "descripcion": "Formación general con internado rotatorio.",
        "fecha_inicio": "2012-02-01",
        "fecha_fin": "2018-12-15",
        "is_actual": False,
        "is_visible": True,
        "orden": 0,
    },
    {
        "institucion": "Hospital del Niño Dr. Ovidio Aliaga Uría",
        "titulo": "Especialidad en Pediatría",
        "area_estudio": "Pediatría",
        "descripcion": "Residencia de tres años en pediatría clínica.",
        "fecha_inicio": "2019-03-01",
        "fecha_fin": "2022-02-28",
        "is_actual": False,
        "is_visible": True,
        "orden": 1,
    },
    {
        "institucion": "Universidad Católica Boliviana",
        "titulo": "Diplomado en Gestión Hospitalaria",
        "area_estudio": "Gestión en salud",
        "descripcion": "Programa ejecutivo de fin de semana.",
        "fecha_inicio": "2023-08-01",
        "fecha_fin": "2024-06-30",
        "is_actual": False,
        "is_visible": False,
        "orden": 2,
    },
]
TARJETA_EDUCACION_RESPONSE_EXAMPLES = response_examples(
    TARJETA_EDUCACION_CREATE_EXAMPLES, _IDS, tarjeta_id=TARJETA_ID_EXAMPLE
)
TARJETA_EDUCACION_PUBLIC_EXAMPLES = pick(
    TARJETA_EDUCACION_RESPONSE_EXAMPLES,
    "id",
    "institucion",
    "titulo",
    "area_estudio",
    "descripcion",
    "fecha_inicio",
    "fecha_fin",
    "is_actual",
)
TARJETA_EDUCACION_NESTED_EXAMPLES = nested_examples(TARJETA_EDUCACION_CREATE_EXAMPLES, _IDS)

TARJETA_EDUCACION_CREATE_EXAMPLE = TARJETA_EDUCACION_CREATE_EXAMPLES[0]
TARJETA_EDUCACION_RESPONSE_EXAMPLE = TARJETA_EDUCACION_RESPONSE_EXAMPLES[0]
TARJETA_EDUCACION_PUBLIC_EXAMPLE = TARJETA_EDUCACION_PUBLIC_EXAMPLES[0]

TARJETA_EDUCACION_MAX = 10


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaEducacionCreate(SchemaBase):
    """Hija embebida de la tarjeta: tarjeta_id lo asigna el service."""

    institucion: str = Field(max_length=200)
    titulo: str | None = Field(default=None, max_length=200)
    area_estudio: str | None = Field(default=None, max_length=200)
    descripcion: str | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    is_actual: bool = False
    is_visible: bool = True
    orden: int = Field(default=0, le=SMALLINT_MAX)

    @field_validator("institucion", mode="before")
    @classmethod
    def validate_institucion(cls, value: object) -> str:
        return validator_non_empty_text(value)

    @field_validator("titulo", "area_estudio", "descripcion", mode="before")
    @classmethod
    def validate_texto_opcional(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("fecha_inicio", "fecha_fin", mode="before")
    @classmethod
    def validate_fecha(cls, value: object) -> date | None:
        return None if value is None else validator_date(value)

    @field_validator("is_actual", "is_visible", mode="before")
    @classmethod
    def validate_booleano(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    @model_validator(mode="after")
    def validate_fechas(self) -> Self:
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha de fin no puede ser anterior a la de inicio.")
        if self.is_actual and self.fecha_fin is not None:
            raise ValueError("Un estudio actual no tiene fecha de fin.")
        return self

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_EDUCACION_CREATE_EXAMPLE})


class TarjetaEducacionResponse(SchemaBase):
    id: UUID
    tarjeta_id: UUID
    institucion: str
    titulo: str | None
    area_estudio: str | None
    descripcion: str | None
    fecha_inicio: date | None
    fecha_fin: date | None
    is_actual: bool
    is_visible: bool
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_EDUCACION_RESPONSE_EXAMPLE})


class TarjetaEducacionResponseAudit(AuditMixin, TarjetaEducacionResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_EDUCACION_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class TarjetaEducacionPublic(SchemaBase):
    id: UUID
    institucion: str
    titulo: str | None
    area_estudio: str | None
    descripcion: str | None
    fecha_inicio: date | None
    fecha_fin: date | None
    is_actual: bool

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_EDUCACION_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class TarjetaEducacionNestedItem(TarjetaEducacionCreate):
    """Elemento de la lista del padre: con id se actualiza, sin id se crea (AGENTS.md §20)."""

    id: UUID | None = None

    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_EDUCACION_CREATE_EXAMPLE, "id": _ID}})
