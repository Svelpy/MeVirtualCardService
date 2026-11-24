"""
Ejemplos de Swagger (AGENTS.md §20). El frontend aprende cada schema por su
ejemplo, así que:

- el ejemplo trae todos los campos del schema y ninguno va null ni vacío;
- toda lista trae al menos 3 objetos distintos (EXAMPLE_COUNT): un solo
  elemento no muestra la variedad (orden, flags, opcionales);
- un campo que el backend rechaza en ese contexto no se muestra.

Cada hija define sus 3 variantes de <X>Create y deriva de ellas las de
<X>Response, <X>Public y <X>NestedItem con estas funciones.
tests/test_schema_examples.py lo verifica sobre el OpenAPI publicado.
"""

from collections.abc import Sequence
from typing import Any


EXAMPLE_COUNT = 3

TARJETA_ID_EXAMPLE = "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b"

TIMESTAMP_EXAMPLES: tuple[dict[str, str], ...] = (
    {"created_at": "2026-01-15T14:30:00Z", "updated_at": "2026-02-01T09:00:00Z"},
    {"created_at": "2026-01-15T14:31:00Z", "updated_at": "2026-01-20T11:15:00Z"},
    {"created_at": "2026-01-16T10:00:00Z", "updated_at": "2026-02-03T16:45:00Z"},
)

Example = dict[str, Any]


def response_examples(creates: Sequence[Example], ids: Sequence[str], **parent: Any) -> list[Example]:
    """<X>Response: id, la foreign key de dueño, los campos del Create y sus fechas."""
    return [
        {"id": id_, **parent, **create, **TIMESTAMP_EXAMPLES[index % len(TIMESTAMP_EXAMPLES)]}
        for index, (id_, create) in enumerate(zip(ids, creates, strict=True))
    ]


def nested_examples(creates: Sequence[Example], ids: Sequence[str]) -> list[Example]:
    """<X>NestedItem: el Create con su id (con id se actualiza)."""
    return [{**create, "id": id_} for id_, create in zip(ids, creates, strict=True)]


def pick(examples: Sequence[Example], *fields: str) -> list[Example]:
    """Solo esos campos de cada ejemplo, en ese orden (por ejemplo, para <X>Public)."""
    return [{field: example[field] for field in fields} for example in examples]


def merge(examples: Sequence[Example], extras: Sequence[Example]) -> list[Example]:
    """Agrega a cada ejemplo sus relaciones (por ejemplo, los nietos de cada hija)."""
    return [{**example, **extra} for example, extra in zip(examples, extras, strict=True)]


def without(examples: Sequence[Example], *fields: str) -> list[Example]:
    """Cada ejemplo sin esos campos: los que el backend rechaza en ese contexto."""
    return [{key: value for key, value in example.items() if key not in fields} for example in examples]
