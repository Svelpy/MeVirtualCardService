from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domains.vitrina_categoria.schemas import (
    VITRINA_CATEGORIA_REF_EXAMPLE,
    VITRINA_CATEGORIA_RESPONSE_EXAMPLE,
    VitrinaCategoriaRef,
    VitrinaCategoriaResponse,
)
from app.domains.vitrina_item_imagen.schemas import (
    VITRINA_ITEM_IMAGEN_CREATE_EXAMPLE,
    VITRINA_ITEM_IMAGEN_MAX,
    VITRINA_ITEM_IMAGEN_PUBLIC_EXAMPLE,
    VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLE,
    VitrinaItemImagenCreate,
    VitrinaItemImagenNestedItem,
    VitrinaItemImagenPublic,
    VitrinaItemImagenResponse,
    ensure_one_principal,
)
from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase, reject_null
from app.shared.services.validators import (
    validator_boolean,
    validator_non_empty_text,
    validator_non_negative_integer,
    validator_non_negative_money,
    validator_unique_ids,
)


_ID = "e4da3b7f-bbce-4a4b-8f3c-2d1e0f9a8b7c"
_VITRINA_ID = "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b"
_CATEGORIA_ID = "1f0e3dad-9990-4345-8b6a-5c4d3e2f1a09"

_CAMPOS_EXAMPLE = {
    "titulo": "Consulta pediátrica",
    "descripcion": "Evaluación general, control de crecimiento y orientación a padres.",
    "precio": "250.00",
    "precio_anterior": "300.00",
    "precio_etiqueta": "por sesión",
    "campo1": "45 minutos",
    "campo2": "Presencial",
    "campo3": "0 a 14 años",
    "campo4": "Informe escrito",
    "destacado": True,
    "is_visible": True,
    "orden": 0,
}
VITRINA_ITEM_CREATE_EXAMPLE = {"vitrina_id": _VITRINA_ID, "categoria_id": _CATEGORIA_ID, **_CAMPOS_EXAMPLE}
VITRINA_ITEM_UPDATE_EXAMPLE = {"categoria_id": _CATEGORIA_ID, **_CAMPOS_EXAMPLE}
VITRINA_ITEM_RESPONSE_EXAMPLE = {
    "id": _ID,
    **VITRINA_ITEM_CREATE_EXAMPLE,
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
VITRINA_ITEM_PUBLIC_EXAMPLE = {
    "id": _ID,
    "categoria_id": _CATEGORIA_ID,
    "titulo": "Consulta pediátrica",
    "descripcion": "Evaluación general, control de crecimiento y orientación a padres.",
    "precio": "250.00",
    "precio_anterior": "300.00",
    "precio_etiqueta": "por sesión",
    "campo1": "45 minutos",
    "campo2": "Presencial",
    "campo3": "0 a 14 años",
    "campo4": "Informe escrito",
    "destacado": True,
    "imagenes": [VITRINA_ITEM_IMAGEN_PUBLIC_EXAMPLE],
}

_TEXTO_OPCIONAL_FIELDS = ("descripcion", "precio_etiqueta", "campo1", "campo2", "campo3", "campo4")


def _ensure_precio_anterior(precio: Decimal | None, precio_anterior: Decimal | None) -> None:
    if precio_anterior is not None and (precio is None or precio_anterior <= precio):
        raise ValueError("El precio anterior requiere un precio y debe ser mayor que él.")


# =================================
# Ronda 1: schemas planos
# =================================

class VitrinaItemCreate(SchemaBase):
    """Hija paginada de la vitrina: vitrina_id es obligatorio y nunca cambia."""

    vitrina_id: UUID
    # Debe ser una categoría de la misma vitrina; lo comprueba el service.
    categoria_id: UUID | None = None
    titulo: str = Field(max_length=150)
    descripcion: str | None = None
    precio: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)  # NULL = Consultar
    precio_anterior: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    precio_etiqueta: str | None = Field(default=None, max_length=50)
    campo1: str | None = Field(default=None, max_length=100)
    campo2: str | None = Field(default=None, max_length=100)
    campo3: str | None = Field(default=None, max_length=100)
    campo4: str | None = Field(default=None, max_length=100)
    destacado: bool = False
    is_visible: bool = True
    orden: int = Field(default=0, le=SMALLINT_MAX)

    @field_validator("titulo", mode="before")
    @classmethod
    def validate_titulo(cls, value: object) -> str:
        return validator_non_empty_text(value)

    @field_validator(*_TEXTO_OPCIONAL_FIELDS, mode="before")
    @classmethod
    def validate_texto_opcional(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("precio", "precio_anterior", mode="before")
    @classmethod
    def validate_precio(cls, value: object) -> Decimal | None:
        return None if value is None else validator_non_negative_money(value)

    @field_validator("destacado", "is_visible", mode="before")
    @classmethod
    def validate_booleano(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    @model_validator(mode="after")
    def validate_precio_anterior(self) -> Self:
        _ensure_precio_anterior(self.precio, self.precio_anterior)
        return self

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_ITEM_CREATE_EXAMPLE})


class VitrinaItemUpdate(SchemaBase):
    """
    Sin vitrina_id: una hija paginada no cambia de padre. Si solo llega uno de
    los dos precios, la comparación con el valor guardado la hace el service.
    """

    categoria_id: UUID | None = Field(default=None)  # null = sin categoría
    titulo: str = Field(default=None, max_length=150)
    descripcion: str | None = Field(default=None)
    precio: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    precio_anterior: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    precio_etiqueta: str | None = Field(default=None, max_length=50)
    campo1: str | None = Field(default=None, max_length=100)
    campo2: str | None = Field(default=None, max_length=100)
    campo3: str | None = Field(default=None, max_length=100)
    campo4: str | None = Field(default=None, max_length=100)
    destacado: bool = Field(default=None)
    is_visible: bool = Field(default=None)
    orden: int = Field(default=None, le=SMALLINT_MAX)

    @field_validator("titulo", mode="before")
    @classmethod
    def validate_titulo(cls, value: object) -> str:
        return validator_non_empty_text(reject_null(value))

    @field_validator(*_TEXTO_OPCIONAL_FIELDS, mode="before")
    @classmethod
    def validate_texto_opcional(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("precio", "precio_anterior", mode="before")
    @classmethod
    def validate_precio(cls, value: object) -> Decimal | None:
        return None if value is None else validator_non_negative_money(value)

    @field_validator("destacado", "is_visible", mode="before")
    @classmethod
    def validate_booleano(cls, value: object) -> bool:
        return validator_boolean(reject_null(value))

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(reject_null(value))

    @model_validator(mode="after")
    def validate_precio_anterior(self) -> Self:
        if {"precio", "precio_anterior"} <= self.model_fields_set:
            _ensure_precio_anterior(self.precio, self.precio_anterior)
        return self

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_ITEM_UPDATE_EXAMPLE})


class VitrinaItemResponse(SchemaBase):
    id: UUID
    vitrina_id: UUID
    categoria_id: UUID | None
    titulo: str
    descripcion: str | None
    precio: Decimal | None
    precio_anterior: Decimal | None
    precio_etiqueta: str | None
    campo1: str | None
    campo2: str | None
    campo3: str | None
    campo4: str | None
    destacado: bool
    is_visible: bool
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_ITEM_RESPONSE_EXAMPLE})


class VitrinaItemResponseAudit(AuditMixin, VitrinaItemResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**VITRINA_ITEM_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class VitrinaItemPublic(SchemaBase):
    """Item visible de una tarjeta publicada. Si la vitrina oculta precios, el service los quita."""

    id: UUID
    categoria_id: UUID | None
    titulo: str
    descripcion: str | None
    precio: Decimal | None
    precio_anterior: Decimal | None
    precio_etiqueta: str | None
    campo1: str | None
    campo2: str | None
    campo3: str | None
    campo4: str | None
    destacado: bool
    imagenes: list[VitrinaItemImagenPublic]

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_ITEM_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class VitrinaItemCreateNested(VitrinaItemCreate):
    """POST /vitrina-items: el item con sus imágenes."""

    imagenes: list[VitrinaItemImagenCreate] = Field(default_factory=list, max_length=VITRINA_ITEM_IMAGEN_MAX)

    @field_validator("imagenes", mode="after")
    @classmethod
    def validate_imagenes(cls, value: list[VitrinaItemImagenCreate]) -> list[VitrinaItemImagenCreate]:
        ensure_one_principal(value)
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {**VITRINA_ITEM_CREATE_EXAMPLE, "imagenes": [VITRINA_ITEM_IMAGEN_CREATE_EXAMPLE]}
        }
    )


class VitrinaItemUpdateNested(VitrinaItemUpdate):
    """PATCH /vitrina-items/{id}: imagenes es el estado final deseado; ausente o null, no se toca."""

    imagenes: list[VitrinaItemImagenNestedItem] | None = Field(default=None, max_length=VITRINA_ITEM_IMAGEN_MAX)

    @field_validator("imagenes", mode="after")
    @classmethod
    def validate_imagenes(
        cls, value: list[VitrinaItemImagenNestedItem] | None
    ) -> list[VitrinaItemImagenNestedItem] | None:
        if value is None:
            return None
        ensure_one_principal(value)
        return validator_unique_ids(value)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **VITRINA_ITEM_UPDATE_EXAMPLE,
                "imagenes": [{**VITRINA_ITEM_IMAGEN_CREATE_EXAMPLE, "id": VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLE["id"]}],
            }
        }
    )


class VitrinaItemResponseItemList(VitrinaItemResponse):
    categoria: VitrinaCategoriaRef | None

    model_config = ConfigDict(
        json_schema_extra={"example": {**VITRINA_ITEM_RESPONSE_EXAMPLE, "categoria": VITRINA_CATEGORIA_REF_EXAMPLE}}
    )


class VitrinaItemResponseDetail(VitrinaItemResponse):
    categoria: VitrinaCategoriaResponse | None
    imagenes: list[VitrinaItemImagenResponse]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **VITRINA_ITEM_RESPONSE_EXAMPLE,
                "categoria": VITRINA_CATEGORIA_RESPONSE_EXAMPLE,
                "imagenes": [VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLE],
            }
        }
    )
