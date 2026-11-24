from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.domains.vitrina_categoria.schemas import (
    VITRINA_CATEGORIA_IDS,
    VITRINA_CATEGORIA_RESPONSE_EXAMPLES,
    VitrinaCategoriaResponse,
)
from app.domains.vitrina_item_imagen.schemas import (
    VITRINA_ITEM_IMAGEN_CREATE_EXAMPLES,
    VITRINA_ITEM_IMAGEN_MAX,
    VITRINA_ITEM_IMAGEN_NESTED_EXAMPLES,
    VITRINA_ITEM_IMAGEN_PUBLIC_EXAMPLES,
    VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLES,
    VitrinaItemImagenCreate,
    VitrinaItemImagenNestedItem,
    VitrinaItemImagenPublic,
    VitrinaItemImagenResponse,
    ensure_one_principal,
)
from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase
from app.shared.schemas.examples import TARJETA_ID_EXAMPLE, merge, nested_examples, pick, response_examples
from app.shared.services.validators import (
    validator_boolean,
    validator_non_empty_text,
    validator_non_negative_integer,
    validator_non_negative_money,
    validator_unique_ids,
)


_IDS = (
    "e4da3b7f-bbce-4a4b-8f3c-2d1e0f9a8b7c",
    "e4da3b7f-bbce-4a4b-8f3c-2d1e0f9a8b7d",
    "e4da3b7f-bbce-4a4b-8f3c-2d1e0f9a8b7e",
)
_ID = _IDS[0]

# Cada item usa una de las categorías de ejemplo de su vitrina.
VITRINA_ITEM_CREATE_EXAMPLES = [
    {
        "categoria_id": VITRINA_CATEGORIA_IDS[0],
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
    },
    {
        "categoria_id": VITRINA_CATEGORIA_IDS[1],
        "titulo": "Paquete control del primer año",
        "descripcion": "Seis controles de niño sano durante el primer año de vida.",
        "precio": "1200.00",
        "precio_anterior": "1500.00",
        "precio_etiqueta": "desde",
        "campo1": "6 sesiones",
        "campo2": "Presencial",
        "campo3": "0 a 12 meses",
        "campo4": "Carnet de vacunas al día",
        "destacado": False,
        "is_visible": True,
        "orden": 1,
    },
    {
        "categoria_id": VITRINA_CATEGORIA_IDS[0],
        "titulo": "Teleconsulta de seguimiento",
        "descripcion": "Revisión de resultados y ajuste de tratamiento por videollamada.",
        "precio": "150.00",
        "precio_anterior": "180.00",
        "precio_etiqueta": "por llamada",
        "campo1": "20 minutos",
        "campo2": "Virtual",
        "campo3": "Pacientes en tratamiento",
        "campo4": "Receta digital",
        "destacado": False,
        "is_visible": False,
        "orden": 2,
    },
]
VITRINA_ITEM_RESPONSE_EXAMPLES = response_examples(VITRINA_ITEM_CREATE_EXAMPLES, _IDS, vitrina_id=TARJETA_ID_EXAMPLE)
VITRINA_ITEM_PUBLIC_EXAMPLES = merge(
    pick(
        VITRINA_ITEM_RESPONSE_EXAMPLES,
        "id",
        "categoria_id",
        "titulo",
        "descripcion",
        "precio",
        "precio_anterior",
        "precio_etiqueta",
        "campo1",
        "campo2",
        "campo3",
        "campo4",
        "destacado",
    ),
    [{"imagenes": VITRINA_ITEM_IMAGEN_PUBLIC_EXAMPLES}] * len(_IDS),
)
VITRINA_ITEM_CREATE_NESTED_EXAMPLES = merge(
    VITRINA_ITEM_CREATE_EXAMPLES, [{"imagenes": VITRINA_ITEM_IMAGEN_CREATE_EXAMPLES}] * len(_IDS)
)
VITRINA_ITEM_NESTED_EXAMPLES = nested_examples(
    merge(VITRINA_ITEM_CREATE_EXAMPLES, [{"imagenes": VITRINA_ITEM_IMAGEN_NESTED_EXAMPLES}] * len(_IDS)), _IDS
)
_CATEGORIAS = {categoria["id"]: categoria for categoria in VITRINA_CATEGORIA_RESPONSE_EXAMPLES}
VITRINA_ITEM_RESPONSE_DETAIL_EXAMPLES = merge(
    VITRINA_ITEM_RESPONSE_EXAMPLES,
    [
        {
            "categoria": _CATEGORIAS[item["categoria_id"]],
            "imagenes": [{**imagen, "item_id": item["id"]} for imagen in VITRINA_ITEM_IMAGEN_RESPONSE_EXAMPLES],
        }
        for item in VITRINA_ITEM_RESPONSE_EXAMPLES
    ],
)

VITRINA_ITEM_CREATE_EXAMPLE = VITRINA_ITEM_CREATE_EXAMPLES[0]
VITRINA_ITEM_RESPONSE_EXAMPLE = VITRINA_ITEM_RESPONSE_EXAMPLES[0]
VITRINA_ITEM_PUBLIC_EXAMPLE = VITRINA_ITEM_PUBLIC_EXAMPLES[0]
VITRINA_ITEM_CREATE_NESTED_EXAMPLE = VITRINA_ITEM_CREATE_NESTED_EXAMPLES[0]
VITRINA_ITEM_RESPONSE_DETAIL_EXAMPLE = VITRINA_ITEM_RESPONSE_DETAIL_EXAMPLES[0]

# Hija embebida de la vitrina: "contengo pocos".
VITRINA_ITEM_MAX = 25

_TEXTO_OPCIONAL_FIELDS = ("descripcion", "precio_etiqueta", "campo1", "campo2", "campo3", "campo4")


def _ensure_precio_anterior(precio: Decimal | None, precio_anterior: Decimal | None) -> None:
    if precio_anterior is not None and (precio is None or precio_anterior <= precio):
        raise ValueError("El precio anterior requiere un precio y debe ser mayor que él.")


# =================================
# Ronda 1: schemas planos
# =================================

class VitrinaItemCreate(SchemaBase):
    """Hija embebida de la vitrina: vitrina_id lo asigna el service."""

    # Debe ser una categoría existente de la misma vitrina; lo comprueba el service.
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
    """Item visible de una tarjeta publicada. Si la vitrina oculta precios, VitrinaPublic los quita."""

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
    """Item con sus imágenes, creado dentro de la vitrina."""

    imagenes: list[VitrinaItemImagenCreate] = Field(default_factory=list, max_length=VITRINA_ITEM_IMAGEN_MAX)

    @field_validator("imagenes", mode="after")
    @classmethod
    def validate_imagenes(cls, value: list[VitrinaItemImagenCreate]) -> list[VitrinaItemImagenCreate]:
        ensure_one_principal(value)
        return value

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_ITEM_CREATE_NESTED_EXAMPLE})


class VitrinaItemNestedItem(VitrinaItemCreateNested):
    """
    Elemento de la lista de items de la vitrina: con id se actualiza, sin id se
    crea. imagenes es el estado final deseado; ausente o null, no se toca.
    """

    imagenes: list[VitrinaItemImagenNestedItem] | None = Field(default=None, max_length=VITRINA_ITEM_IMAGEN_MAX)
    id: UUID | None = None

    @field_validator("imagenes", mode="after")
    @classmethod
    def validate_imagenes(
        cls, value: list[VitrinaItemImagenNestedItem] | None
    ) -> list[VitrinaItemImagenNestedItem] | None:
        if value is None:
            return None
        ensure_one_principal(value)
        return validator_unique_ids(value)

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_ITEM_NESTED_EXAMPLES[0]})


class VitrinaItemResponseDetail(VitrinaItemResponse):
    categoria: VitrinaCategoriaResponse | None
    imagenes: list[VitrinaItemImagenResponse]

    model_config = ConfigDict(json_schema_extra={"example": VITRINA_ITEM_RESPONSE_DETAIL_EXAMPLE})
