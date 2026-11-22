from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CHAR, String
from sqlmodel import Field, Relationship

from app.core.base_model import BaseModel

if TYPE_CHECKING:
    from app.domains.vitrina_categoria.models import VitrinaCategoria


class Vitrina(BaseModel, table=True):
    """Extensión 1:1 de la tarjeta: su id es el id de la tarjeta (AGENTS.md §18)."""

    __tablename__ = "vitrina"

    id: UUID = Field(foreign_key="tarjeta.id", primary_key=True)
    mostrar_precios: bool = Field(default=True, nullable=False)
    moneda: str = Field(default="BOB", sa_type=CHAR(3), nullable=False)  # ISO 4217
    # NULL = campo no usado.
    campo1_nombre: str | None = Field(default=None, sa_type=String(40), nullable=True)
    campo2_nombre: str | None = Field(default=None, sa_type=String(40), nullable=True)
    campo3_nombre: str | None = Field(default=None, sa_type=String(40), nullable=True)
    campo4_nombre: str | None = Field(default=None, sa_type=String(40), nullable=True)

    # Hijas embebidas. Los items son hijas paginadas: se listan con ?vitrina_id=.
    categorias: list["VitrinaCategoria"] = Relationship(
        sa_relationship_kwargs={"lazy": "raise", "order_by": "[VitrinaCategoria.orden, VitrinaCategoria.created_at]"}
    )
