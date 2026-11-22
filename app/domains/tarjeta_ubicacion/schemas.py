from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domains.ubicacion_horario.schemas import (
    UBICACION_HORARIO_CREATE_EXAMPLE,
    UBICACION_HORARIO_MAX,
    UBICACION_HORARIO_PUBLIC_EXAMPLE,
    UBICACION_HORARIO_RESPONSE_EXAMPLE,
    UbicacionHorarioCreate,
    UbicacionHorarioNestedItem,
    UbicacionHorarioPublic,
    UbicacionHorarioResponse,
    ensure_no_overlap,
)
from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase
from app.shared.services.validators import (
    validator_boolean,
    validator_https_url,
    validator_latitude,
    validator_longitude,
    validator_non_empty_text,
    validator_non_negative_integer,
    validator_unique_ids,
)


_ID = "1679091c-5a88-4faf-8c1b-0a9b8c7d6e5f"

TARJETA_UBICACION_CREATE_EXAMPLE = {
    "nombre": "Consultorio Norte",
    "direccion": "Av. Arce 2631, Edificio Torre Azul, piso 4",
    "ciudad": "La Paz",
    "departamento": "La Paz",
    "pais": "Bolivia",
    "maps_url": "https://maps.app.goo.gl/AbCdEf123456",
    "lat": "-16.509710",
    "lng": "-68.123920",
    "is_visible": True,
    "orden": 0,
}
TARJETA_UBICACION_RESPONSE_EXAMPLE = {
    "id": _ID,
    "tarjeta_id": "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b",
    **TARJETA_UBICACION_CREATE_EXAMPLE,
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
TARJETA_UBICACION_PUBLIC_EXAMPLE = {
    "id": _ID,
    "nombre": "Consultorio Norte",
    "direccion": "Av. Arce 2631, Edificio Torre Azul, piso 4",
    "ciudad": "La Paz",
    "departamento": "La Paz",
    "pais": "Bolivia",
    "maps_url": "https://maps.app.goo.gl/AbCdEf123456",
    "lat": "-16.509710",
    "lng": "-68.123920",
    "horarios": [UBICACION_HORARIO_PUBLIC_EXAMPLE],
}

TARJETA_UBICACION_MAX = 10


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaUbicacionCreate(SchemaBase):
    """Hija embebida de la tarjeta: tarjeta_id lo asigna el service."""

    nombre: str | None = Field(default=None, max_length=150)
    direccion: str = Field(max_length=255)
    ciudad: str | None = Field(default=None, max_length=100)
    departamento: str | None = Field(default=None, max_length=100)
    pais: str | None = Field(default=None, max_length=100)
    maps_url: str | None = None
    lat: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    lng: Decimal | None = Field(default=None, max_digits=9, decimal_places=6)
    is_visible: bool = True
    orden: int = Field(default=0, le=SMALLINT_MAX)

    @field_validator("direccion", mode="before")
    @classmethod
    def validate_direccion(cls, value: object) -> str:
        return validator_non_empty_text(value)

    @field_validator("nombre", "ciudad", "departamento", "pais", mode="before")
    @classmethod
    def validate_texto_opcional(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("maps_url", mode="before")
    @classmethod
    def validate_maps_url(cls, value: object) -> str | None:
        return None if value is None else validator_https_url(value)

    @field_validator("lat", mode="before")
    @classmethod
    def validate_lat(cls, value: object) -> Decimal | None:
        return None if value is None else validator_latitude(value)

    @field_validator("lng", mode="before")
    @classmethod
    def validate_lng(cls, value: object) -> Decimal | None:
        return None if value is None else validator_longitude(value)

    @field_validator("is_visible", mode="before")
    @classmethod
    def validate_is_visible(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    @model_validator(mode="after")
    def validate_coordenadas(self) -> Self:
        if (self.lat is None) != (self.lng is None):
            raise ValueError("La latitud y la longitud se envían juntas.")
        return self

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_UBICACION_CREATE_EXAMPLE})


class TarjetaUbicacionResponse(SchemaBase):
    id: UUID
    tarjeta_id: UUID
    nombre: str | None
    direccion: str
    ciudad: str | None
    departamento: str | None
    pais: str | None
    maps_url: str | None
    lat: Decimal | None
    lng: Decimal | None
    is_visible: bool
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_UBICACION_RESPONSE_EXAMPLE})


class TarjetaUbicacionResponseAudit(AuditMixin, TarjetaUbicacionResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_UBICACION_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class TarjetaUbicacionPublic(SchemaBase):
    id: UUID
    nombre: str | None
    direccion: str
    ciudad: str | None
    departamento: str | None
    pais: str | None
    maps_url: str | None
    lat: Decimal | None
    lng: Decimal | None
    horarios: list[UbicacionHorarioPublic]

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_UBICACION_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

TARJETA_UBICACION_CREATE_NESTED_EXAMPLE = {
    **TARJETA_UBICACION_CREATE_EXAMPLE,
    "horarios": [UBICACION_HORARIO_CREATE_EXAMPLE],
}
TARJETA_UBICACION_RESPONSE_DETAIL_EXAMPLE = {
    **TARJETA_UBICACION_RESPONSE_EXAMPLE,
    "horarios": [UBICACION_HORARIO_RESPONSE_EXAMPLE],
}


class TarjetaUbicacionCreateNested(TarjetaUbicacionCreate):
    """Ubicación con sus horarios, creada dentro de la tarjeta."""

    horarios: list[UbicacionHorarioCreate] = Field(default_factory=list, max_length=UBICACION_HORARIO_MAX)

    @field_validator("horarios", mode="after")
    @classmethod
    def validate_horarios(cls, value: list[UbicacionHorarioCreate] | None) -> list[UbicacionHorarioCreate] | None:
        if value is not None:
            ensure_no_overlap(value)
        return value

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_UBICACION_CREATE_NESTED_EXAMPLE})


class TarjetaUbicacionNestedItem(TarjetaUbicacionCreateNested):
    """
    Elemento de la lista de ubicaciones de la tarjeta: con id se actualiza, sin
    id se crea. horarios es el estado final deseado; ausente o null, no se toca.
    """

    horarios: list[UbicacionHorarioNestedItem] | None = Field(default=None, max_length=UBICACION_HORARIO_MAX)
    id: UUID | None = None

    @field_validator("horarios", mode="after")
    @classmethod
    def validate_horarios_ids(
        cls, value: list[UbicacionHorarioNestedItem] | None
    ) -> list[UbicacionHorarioNestedItem] | None:
        return None if value is None else validator_unique_ids(value)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **TARJETA_UBICACION_CREATE_EXAMPLE,
                "horarios": [{**UBICACION_HORARIO_CREATE_EXAMPLE, "id": UBICACION_HORARIO_RESPONSE_EXAMPLE["id"]}],
                "id": _ID,
            }
        }
    )


class TarjetaUbicacionResponseDetail(TarjetaUbicacionResponse):
    horarios: list[UbicacionHorarioResponse]

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_UBICACION_RESPONSE_DETAIL_EXAMPLE})
