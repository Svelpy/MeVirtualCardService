from datetime import datetime
from uuid import UUID

from typing import Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domains.vitrina_categoria.schemas import (
    VITRINA_CATEGORIA_CREATE_EXAMPLE,
    VITRINA_CATEGORIA_ID,
    VITRINA_CATEGORIA_MAX,
    VITRINA_CATEGORIA_PUBLIC_EXAMPLE,
    VITRINA_CATEGORIA_RESPONSE_EXAMPLE,
    VitrinaCategoriaCreate,
    VitrinaCategoriaNestedItem,
    VitrinaCategoriaPublic,
    VitrinaCategoriaResponse,
    ensure_unique_nombre,
)
from app.domains.vitrina_item.schemas import (
    VITRINA_ITEM_CREATE_NESTED_EXAMPLE,
    VITRINA_ITEM_MAX,
    VITRINA_ITEM_PUBLIC_EXAMPLE,
    VITRINA_ITEM_RESPONSE_DETAIL_EXAMPLE,
    VitrinaItemCreateNested,
    VitrinaItemNestedItem,
    VitrinaItemPublic,
    VitrinaItemResponseDetail,
)
from app.shared.schemas.base import AUDIT_EXAMPLE, AuditMixin, SchemaBase, reject_null
from app.shared.services.validators import (
    validator_boolean,
    validator_currency_code,
    validator_non_empty_text,
    validator_unique_ids,
)


_CAMPOS_EXAMPLE = {
    "mostrar_precios": True,
    "moneda": "BOB",
    "campo1_nombre": "Duración",
    "campo2_nombre": "Modalidad",
    "campo3_nombre": "Edad",
    "campo4_nombre": "Incluye",
}
VITRINA_CREATE_EXAMPLE = _CAMPOS_EXAMPLE
VITRINA_RESPONSE_EXAMPLE = {
    "id": "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b",
    **_CAMPOS_EXAMPLE,
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
VITRINA_PUBLIC_EXAMPLE = {
    **_CAMPOS_EXAMPLE,
    "categorias": [VITRINA_CATEGORIA_PUBLIC_EXAMPLE],
    "items": [VITRINA_ITEM_PUBLIC_EXAMPLE],
}

_CAMPO_NOMBRE_FIELDS = ("campo1_nombre", "campo2_nombre", "campo3_nombre", "campo4_nombre")


# =================================
# Ronda 1: schemas planos
# =================================

class VitrinaCreate(SchemaBase):
    """Extensión 1:1: se crea junto con la tarjeta y con su mismo id."""

    mostrar_precios: bool = True
    moneda: str = Field(default="BOB", min_length=3, max_length=3)
    # NULL = campo no usado por los items.
    campo1_nombre: str | None = Field(default=None, max_length=40)
    campo2_nombre: str | None = Field(default=None, max_length=40)
    campo3_nombre: str | None = Field(default=None, max_length=40)
    campo4_nombre: str | None = Field(default=None, max_length=40)

    @field_validator("mostrar_precios", mode="before")
    @classmethod
    def validate_mostrar_precios(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("moneda", mode="before")
    @classmethod
    def validate_moneda(cls, value: object) -> str:
        return validator_currency_code(value)

    @field_validator(*_CAMPO_NOMBRE_FIELDS, mode="before")
    @classmethod
    def validate_campo_nombre(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_CREATE_EXAMPLE})


class VitrinaUpdate(SchemaBase):
    mostrar_precios: bool = Field(default=None)
    moneda: str = Field(default=None, min_length=3, max_length=3)
    campo1_nombre: str | None = Field(default=None, max_length=40)
    campo2_nombre: str | None = Field(default=None, max_length=40)
    campo3_nombre: str | None = Field(default=None, max_length=40)
    campo4_nombre: str | None = Field(default=None, max_length=40)

    @field_validator("mostrar_precios", mode="before")
    @classmethod
    def validate_mostrar_precios(cls, value: object) -> bool:
        return validator_boolean(reject_null(value))

    @field_validator("moneda", mode="before")
    @classmethod
    def validate_moneda(cls, value: object) -> str:
        return validator_currency_code(reject_null(value))

    @field_validator(*_CAMPO_NOMBRE_FIELDS, mode="before")
    @classmethod
    def validate_campo_nombre(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    model_config = ConfigDict(json_schema_extra={"example": _CAMPOS_EXAMPLE})


class VitrinaResponse(SchemaBase):
    id: UUID
    mostrar_precios: bool
    moneda: str
    campo1_nombre: str | None
    campo2_nombre: str | None
    campo3_nombre: str | None
    campo4_nombre: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_RESPONSE_EXAMPLE})


class VitrinaResponseAudit(AuditMixin, VitrinaResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**VITRINA_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class VitrinaPublic(SchemaBase):
    """
    La vitrina con sus categorías visibles y sus items visibles (sin los de una
    categoría oculta). Si mostrar_precios es false, los items salen sin precios.
    """

    mostrar_precios: bool
    moneda: str
    campo1_nombre: str | None
    campo2_nombre: str | None
    campo3_nombre: str | None
    campo4_nombre: str | None
    categorias: list[VitrinaCategoriaPublic]
    items: list[VitrinaItemPublic]

    @model_validator(mode="after")
    def hide_precios(self) -> Self:
        if not self.mostrar_precios:
            for item in self.items:
                item.precio = item.precio_anterior = item.precio_etiqueta = None
        return self

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

VITRINA_CREATE_NESTED_EXAMPLE = {
    **VITRINA_CREATE_EXAMPLE,
    "categorias": [VITRINA_CATEGORIA_CREATE_EXAMPLE],
    "items": [{**VITRINA_ITEM_CREATE_NESTED_EXAMPLE, "categoria_id": None}],
}


class VitrinaCreateNested(VitrinaCreate):
    """
    Vitrina con sus categorías y sus items, creada dentro de la tarjeta. Las
    categorías todavía no tienen id, así que los items se crean sin categoría.
    """

    categorias: list[VitrinaCategoriaCreate] = Field(default_factory=list, max_length=VITRINA_CATEGORIA_MAX)
    items: list[VitrinaItemCreateNested] = Field(default_factory=list, max_length=VITRINA_ITEM_MAX)

    @field_validator("categorias", mode="after")
    @classmethod
    def validate_categorias(cls, value: list[VitrinaCategoriaCreate]) -> list[VitrinaCategoriaCreate]:
        ensure_unique_nombre(value)
        return value

    @field_validator("items", mode="after")
    @classmethod
    def validate_items(cls, value: list[VitrinaItemCreateNested]) -> list[VitrinaItemCreateNested]:
        if any(item.categoria_id is not None for item in value):
            raise ValueError("Al crear la vitrina los items van sin categoría; asígnala al editarla.")
        return value

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_CREATE_NESTED_EXAMPLE})


class VitrinaUpdateNested(VitrinaUpdate):
    """
    PATCH /vitrinas/{id}. categorias e items son el estado final deseado. Un
    item solo puede usar una categoría existente que se conserve; eliminar una
    categoría que usan items no eliminados responde 409 (AGENTS.md §19).
    """

    categorias: list[VitrinaCategoriaNestedItem] | None = Field(default=None, max_length=VITRINA_CATEGORIA_MAX)
    items: list[VitrinaItemNestedItem] | None = Field(default=None, max_length=VITRINA_ITEM_MAX)

    @field_validator("categorias", mode="after")
    @classmethod
    def validate_categorias(
        cls, value: list[VitrinaCategoriaNestedItem] | None
    ) -> list[VitrinaCategoriaNestedItem] | None:
        if value is None:
            return None
        ensure_unique_nombre(value)
        return validator_unique_ids(value)

    @field_validator("items", mode="after")
    @classmethod
    def validate_items(cls, value: list[VitrinaItemNestedItem] | None) -> list[VitrinaItemNestedItem] | None:
        return None if value is None else validator_unique_ids(value)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **_CAMPOS_EXAMPLE,
                "categorias": [{**VITRINA_CATEGORIA_CREATE_EXAMPLE, "id": VITRINA_CATEGORIA_ID}],
                "items": [{**VITRINA_ITEM_CREATE_NESTED_EXAMPLE, "id": VITRINA_ITEM_RESPONSE_DETAIL_EXAMPLE["id"]}],
            }
        }
    )


class VitrinaResponseDetail(VitrinaResponse):
    categorias: list[VitrinaCategoriaResponse]
    items: list[VitrinaItemResponseDetail]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **VITRINA_RESPONSE_EXAMPLE,
                "categorias": [VITRINA_CATEGORIA_RESPONSE_EXAMPLE],
                "items": [VITRINA_ITEM_RESPONSE_DETAIL_EXAMPLE],
            }
        }
    )
