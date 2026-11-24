from collections.abc import Sequence
from math import ceil
from typing import Any, Generic, Self, TypeVar

from pydantic import BaseModel, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Schema genérico de respuesta paginada. Uso: PaginatedResponse[UserResponse]

    Su ejemplo en Swagger es una página con las variantes que declara T en
    PAGE_EXAMPLES (al menos 3, AGENTS.md §20).
    """

    total: int  # Total de registros encontrados
    page: int  # Página actual (empieza en 1)
    per_page: int  # Registros por página
    total_pages: int  # Total de páginas
    data: list[T]  # Lista de objetos tipados

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        json_schema = super().__get_pydantic_json_schema__(core_schema, handler)
        args = cls.__pydantic_generic_metadata__["args"]
        examples: list[dict[str, Any]] | None = getattr(args[0], "PAGE_EXAMPLES", None) if args else None
        if examples:
            handler.resolve_ref_schema(json_schema)["example"] = {
                "total": len(examples),
                "page": 1,
                "per_page": 20,
                "total_pages": 1,
                "data": examples,
            }
        return json_schema

    @classmethod
    def build(cls, items: Sequence[object], *, total: int, page: int, per_page: int) -> Self:
        """
        Arma una página a partir de los models que devuelve el repository: cada
        uno se valida con el schema T leyendo sus atributos.
        """
        return cls.model_validate(
            {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": ceil(total / per_page),
                "data": list(items),
            },
            from_attributes=True,
        )
