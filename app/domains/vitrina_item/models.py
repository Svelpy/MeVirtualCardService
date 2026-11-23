from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Numeric, SmallInteger, String, Text
from sqlmodel import Field, Relationship

from app.core.base_model import BaseModel

if TYPE_CHECKING:
    from app.domains.vitrina_categoria.models import VitrinaCategoria
    from app.domains.vitrina_item_imagen.models import VitrinaItemImagen


class VitrinaItem(BaseModel, table=True):
    """Hija embebida de la vitrina (máximo VITRINA_ITEM_MAX): se escribe desde PATCH /vitrinas/{id}."""

    __tablename__ = "vitrina_item"
    __table_args__ = (
        # Un item solo usa categorías de su misma vitrina. Con categoria_id NULL
        # la foreign key no se comprueba (item sin categoría).
        ForeignKeyConstraint(
            ["categoria_id", "vitrina_id"],
            ["vitrina_categoria.id", "vitrina_categoria.vitrina_id"],
            name="fk_vitrina_item_categoria_id_vitrina_categoria",
        ),
        CheckConstraint("precio IS NULL OR precio >= 0", name="precio_no_negativo"),
        CheckConstraint(
            "precio_anterior IS NULL OR (precio IS NOT NULL AND precio_anterior > precio)",
            name="precio_anterior_mayor",
        ),
    )

    vitrina_id: UUID = Field(foreign_key="vitrina.id", nullable=False, index=True)
    categoria_id: UUID | None = Field(default=None, nullable=True, index=True)
    titulo: str = Field(sa_type=String(150), nullable=False)
    descripcion: str | None = Field(default=None, sa_type=Text, nullable=True)
    precio: Decimal | None = Field(default=None, sa_type=Numeric(12, 2), nullable=True)  # NULL = Consultar
    precio_anterior: Decimal | None = Field(default=None, sa_type=Numeric(12, 2), nullable=True)
    precio_etiqueta: str | None = Field(default=None, sa_type=String(50), nullable=True)  # Desde, por sesión
    campo1: str | None = Field(default=None, sa_type=String(100), nullable=True)
    campo2: str | None = Field(default=None, sa_type=String(100), nullable=True)
    campo3: str | None = Field(default=None, sa_type=String(100), nullable=True)
    campo4: str | None = Field(default=None, sa_type=String(100), nullable=True)
    destacado: bool = Field(default=False, nullable=False)
    is_visible: bool = Field(default=True, nullable=False)
    orden: int = Field(default=0, sa_type=SmallInteger, nullable=False)

    # Referencia. Solo lectura: la foreign key compuesta comparte vitrina_id con
    # la de la vitrina, y categoria_id se asigna directamente.
    categoria: "VitrinaCategoria" = Relationship(sa_relationship_kwargs={"lazy": "raise", "viewonly": True})
    # Hijas embebidas.
    imagenes: list["VitrinaItemImagen"] = Relationship(
        sa_relationship_kwargs={"lazy": "raise", "order_by": "[VitrinaItemImagen.orden, VitrinaItemImagen.created_at]"}
    )
