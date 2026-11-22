from uuid import UUID

from sqlalchemy import Index, SmallInteger, String, Text, text
from sqlmodel import Field

from app.core.base_model import BaseModel


class VitrinaItemImagen(BaseModel, table=True):
    __tablename__ = "vitrina_item_imagen"
    __table_args__ = (
        # Una sola imagen principal (orden = 0) por item.
        Index(
            "uq_vitrina_item_imagen_principal_not_deleted",
            "item_id",
            unique=True,
            postgresql_where=text("orden = 0 AND is_deleted = false"),
        ),
    )

    item_id: UUID = Field(foreign_key="vitrina_item.id", nullable=False, index=True)
    url: str = Field(sa_type=Text, nullable=False)
    alt: str | None = Field(default=None, sa_type=String(150), nullable=True)
    orden: int = Field(default=0, sa_type=SmallInteger, nullable=False)  # 0 = principal
