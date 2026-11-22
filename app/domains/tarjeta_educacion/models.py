from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, SmallInteger, String, Text
from sqlmodel import Field

from app.core.base_model import BaseModel


class TarjetaEducacion(BaseModel, table=True):
    __tablename__ = "tarjeta_educacion"
    __table_args__ = (
        CheckConstraint(
            "fecha_fin IS NULL OR fecha_inicio IS NULL OR fecha_fin >= fecha_inicio",
            name="fechas_ordenadas",
        ),
        CheckConstraint("NOT is_actual OR fecha_fin IS NULL", name="actual_sin_fin"),
    )

    tarjeta_id: UUID = Field(foreign_key="tarjeta.id", nullable=False, index=True)
    institucion: str = Field(sa_type=String(200), nullable=False)
    titulo: str | None = Field(default=None, sa_type=String(200), nullable=True)
    area_estudio: str | None = Field(default=None, sa_type=String(200), nullable=True)
    descripcion: str | None = Field(default=None, sa_type=Text, nullable=True)
    fecha_inicio: date | None = Field(default=None, sa_type=Date, nullable=True)
    fecha_fin: date | None = Field(default=None, sa_type=Date, nullable=True)
    is_actual: bool = Field(default=False, nullable=False)
    is_visible: bool = Field(default=True, nullable=False)
    orden: int = Field(default=0, sa_type=SmallInteger, nullable=False)
