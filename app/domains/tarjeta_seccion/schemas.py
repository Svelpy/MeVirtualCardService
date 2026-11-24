from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.shared.enums import ClaveSeccion
from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase
from app.shared.schemas.examples import (
    TARJETA_ID_EXAMPLE,
    TIMESTAMP_EXAMPLES,
    nested_examples,
    pick,
)
from app.shared.services.validators import (
    validator_boolean,
    validator_non_empty_text,
    validator_non_negative_integer,
)


# Las 8 secciones de una tarjeta, una por ClaveSeccion: la lista siempre las trae todas.
_SECCIONES = (
    ("45c48cce-2e2d-4fbd-aa1a-9b8c7d6e5f40", "acerca", "Sobre mí", True),
    ("45c48cce-2e2d-4fbd-aa1a-9b8c7d6e5f41", "contacto", "Contáctame", True),
    ("45c48cce-2e2d-4fbd-aa1a-9b8c7d6e5f42", "vitrina", "Servicios", True),
    ("45c48cce-2e2d-4fbd-aa1a-9b8c7d6e5f43", "ubicacion", "Dónde atiendo", True),
    ("45c48cce-2e2d-4fbd-aa1a-9b8c7d6e5f44", "redes", "Sígueme", True),
    ("45c48cce-2e2d-4fbd-aa1a-9b8c7d6e5f45", "educacion", "Formación", True),
    ("45c48cce-2e2d-4fbd-aa1a-9b8c7d6e5f46", "certificaciones", "Certificaciones", False),
    ("45c48cce-2e2d-4fbd-aa1a-9b8c7d6e5f47", "faq", "Preguntas frecuentes", True),
)
_IDS = tuple(seccion[0] for seccion in _SECCIONES)
_ID = _IDS[0]

TARJETA_SECCION_CREATE_EXAMPLES = [
    {"titulo": titulo, "is_visible": is_visible, "orden": orden}
    for orden, (_, _, titulo, is_visible) in enumerate(_SECCIONES)
]
TARJETA_SECCION_RESPONSE_EXAMPLES = [
    {
        "id": id_,
        "tarjeta_id": TARJETA_ID_EXAMPLE,
        "clave": clave,
        **create,
        **TIMESTAMP_EXAMPLES[index % len(TIMESTAMP_EXAMPLES)],
    }
    for index, (create, (id_, clave, _, _)) in enumerate(zip(TARJETA_SECCION_CREATE_EXAMPLES, _SECCIONES))
]
# Solo las visibles, en su orden.
TARJETA_SECCION_PUBLIC_EXAMPLES = pick(
    [example for example in TARJETA_SECCION_RESPONSE_EXAMPLES if example["is_visible"]], "clave", "titulo"
)
TARJETA_SECCION_NESTED_EXAMPLES = nested_examples(TARJETA_SECCION_CREATE_EXAMPLES, _IDS)

TARJETA_SECCION_CREATE_EXAMPLE = TARJETA_SECCION_CREATE_EXAMPLES[0]
TARJETA_SECCION_RESPONSE_EXAMPLE = TARJETA_SECCION_RESPONSE_EXAMPLES[0]
TARJETA_SECCION_PUBLIC_EXAMPLE = TARJETA_SECCION_PUBLIC_EXAMPLES[0]

# Las 8 secciones fijas, una por ClaveSeccion.
TARJETA_SECCION_COUNT = len(ClaveSeccion)


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaSeccionCreate(SchemaBase):
    """
    Hija embebida fija: el service crea las 8 junto con la tarjeta (una por
    clave) y por la API solo se actualizan. La clave no se edita.
    """

    titulo: str | None = Field(default=None, max_length=80)
    is_visible: bool = True
    orden: int = Field(default=0, le=SMALLINT_MAX)

    @field_validator("titulo", mode="before")
    @classmethod
    def validate_titulo(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator("is_visible", mode="before")
    @classmethod
    def validate_is_visible(cls, value: object) -> bool:
        return validator_boolean(value)

    @field_validator("orden", mode="before")
    @classmethod
    def validate_orden(cls, value: object) -> int:
        return validator_non_negative_integer(value)

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SECCION_CREATE_EXAMPLE})


class TarjetaSeccionResponse(SchemaBase):
    id: UUID
    tarjeta_id: UUID
    clave: ClaveSeccion
    titulo: str | None
    is_visible: bool
    orden: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SECCION_RESPONSE_EXAMPLE})


class TarjetaSeccionResponseAudit(AuditMixin, TarjetaSeccionResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_SECCION_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class TarjetaSeccionPublic(SchemaBase):
    """Solo las secciones visibles, en su orden."""

    clave: ClaveSeccion
    titulo: str | None

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_SECCION_PUBLIC_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class TarjetaSeccionNestedItem(TarjetaSeccionCreate):
    """Elemento de la lista fija de la tarjeta: el id es obligatorio, porque las 8 secciones ya existen y por la API solo se actualizan."""

    id: UUID

    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_SECCION_CREATE_EXAMPLE, "id": _ID}})
