from collections.abc import Sequence
from datetime import datetime, time
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, field_serializer, field_validator, model_validator

from app.shared.schemas.base import AUDIT_EXAMPLE, AuditMixin, SchemaBase
from app.shared.services.validators import validator_integer, validator_time


_ID = "d3d94468-02a4-4c3b-9b8e-6f5e4d3c2b1a"

UBICACION_HORARIO_CREATE_EXAMPLE = {"dia_semana": 1, "hora_inicio": "08:30", "hora_fin": "12:30"}
UBICACION_HORARIO_RESPONSE_EXAMPLE = {
    "id": _ID,
    "ubicacion_id": "1679091c-5a88-4faf-8c1b-0a9b8c7d6e5f",
    **UBICACION_HORARIO_CREATE_EXAMPLE,
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
UBICACION_HORARIO_PUBLIC_EXAMPLE = UBICACION_HORARIO_CREATE_EXAMPLE

# Tres tramos por día durante la semana.
UBICACION_HORARIO_MAX = 21


def ensure_no_overlap[T](items: Sequence[T]) -> None:
    """
    Rechaza tramos que se solapan en un mismo día; lo usa la lista de la
    ubicación. Tramos contiguos (uno termina cuando empieza el otro) se aceptan.
    """
    by_day: dict[int, list[tuple[time, time]]] = {}
    for item in items:
        by_day.setdefault(getattr(item, "dia_semana"), []).append(
            (getattr(item, "hora_inicio"), getattr(item, "hora_fin"))
        )
    for tramos in by_day.values():
        tramos.sort()
        for (_, fin_anterior), (inicio, _) in zip(tramos, tramos[1:]):
            if inicio < fin_anterior:
                raise ValueError("Hay tramos horarios que se solapan en un mismo día.")


# =================================
# Ronda 1: schemas planos
# =================================

class UbicacionHorarioCreate(SchemaBase):
    """Hija embebida de la ubicación: ubicacion_id lo asigna el service. No cruza la medianoche."""

    dia_semana: int = Field(ge=1, le=7)  # 1 lunes a 7 domingo
    hora_inicio: time
    hora_fin: time

    @field_validator("dia_semana", mode="before")
    @classmethod
    def validate_dia_semana(cls, value: object) -> int:
        return validator_integer(value)

    @field_validator("hora_inicio", "hora_fin", mode="before")
    @classmethod
    def validate_hora(cls, value: object) -> time:
        return validator_time(value)

    @model_validator(mode="after")
    def validate_tramo(self) -> Self:
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("La hora de fin debe ser posterior a la de inicio.")
        return self

    model_config = ConfigDict(json_schema_extra={"example": UBICACION_HORARIO_CREATE_EXAMPLE})


class UbicacionHorarioResponse(SchemaBase):
    id: UUID
    ubicacion_id: UUID
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    created_at: datetime
    updated_at: datetime

    # Se devuelven como HH:MM, el mismo formato que se recibe.
    @field_serializer("hora_inicio", "hora_fin")
    def serialize_hora(self, value: time) -> str:
        return value.strftime("%H:%M")

    model_config = ConfigDict(json_schema_extra={"example": UBICACION_HORARIO_RESPONSE_EXAMPLE})


class UbicacionHorarioResponseAudit(AuditMixin, UbicacionHorarioResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**UBICACION_HORARIO_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class UbicacionHorarioPublic(SchemaBase):
    dia_semana: int
    hora_inicio: time
    hora_fin: time

    # Se devuelven como HH:MM, el mismo formato que se recibe.
    @field_serializer("hora_inicio", "hora_fin")
    def serialize_hora(self, value: time) -> str:
        return value.strftime("%H:%M")

    model_config = ConfigDict(json_schema_extra={"example": UBICACION_HORARIO_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class UbicacionHorarioNestedItem(UbicacionHorarioCreate):
    """Elemento de la lista del padre: con id se actualiza, sin id se crea (AGENTS.md §20)."""

    id: UUID | None = None

    model_config = ConfigDict(json_schema_extra={"example": {**UBICACION_HORARIO_CREATE_EXAMPLE, "id": _ID}})
