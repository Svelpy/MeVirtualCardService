from collections.abc import Sequence
from math import ceil
from typing import Generic, Self, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Schema genérico de respuesta paginada. Uso: PaginatedResponse[UserResponse]"""

    total: int  # Total de registros encontrados
    page: int  # Página actual (empieza en 1)
    per_page: int  # Registros por página
    total_pages: int  # Total de páginas
    data: list[T]  # Lista de objetos tipados

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
