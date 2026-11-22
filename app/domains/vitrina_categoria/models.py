from uuid import UUID

from sqlalchemy import Index, SmallInteger, String, UniqueConstraint, text
from sqlmodel import Field

from app.core.base_model import BaseModel


class VitrinaCategoria(BaseModel, table=True):
    __tablename__ = "vitrina_categoria"
    __table_args__ = (
        Index(
            "uq_vitrina_categoria_vitrina_id_nombre_not_deleted",
            "vitrina_id",
            "nombre",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        # Destino de la foreign key compuesta de vitrina_item: garantiza que un
        # item solo use categorías de su misma vitrina. No es parcial porque
        # PostgreSQL no acepta un índice parcial como destino de una FK.
        UniqueConstraint("id", "vitrina_id", name="uq_vitrina_categoria_id_vitrina_id"),
    )

    vitrina_id: UUID = Field(foreign_key="vitrina.id", nullable=False)
    nombre: str = Field(sa_type=String(60), nullable=False)
    is_visible: bool = Field(default=True, nullable=False)
    orden: int = Field(default=0, sa_type=SmallInteger, nullable=False)
