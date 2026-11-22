from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, SmallInteger, String, Text
from sqlmodel import Field

from app.core.base_model import BaseModel


class TarjetaCertificacion(BaseModel, table=True):
    __tablename__ = "tarjeta_certificacion"
    __table_args__ = (
        CheckConstraint(
            "fecha_expiracion IS NULL OR fecha_emision IS NULL OR fecha_expiracion >= fecha_emision",
            name="fechas_ordenadas",
        ),
        CheckConstraint("NOT no_expira OR fecha_expiracion IS NULL", name="sin_expiracion"),
    )

    tarjeta_id: UUID = Field(foreign_key="tarjeta.id", nullable=False, index=True)
    nombre: str = Field(sa_type=String(200), nullable=False)
    entidad_emisora: str | None = Field(default=None, sa_type=String(200), nullable=True)
    codigo_credencial: str | None = Field(default=None, sa_type=String(150), nullable=True)
    url_credencial: str | None = Field(default=None, sa_type=Text, nullable=True)
    fecha_emision: date | None = Field(default=None, sa_type=Date, nullable=True)
    fecha_expiracion: date | None = Field(default=None, sa_type=Date, nullable=True)
    no_expira: bool = Field(default=False, nullable=False)
    descripcion: str | None = Field(default=None, sa_type=Text, nullable=True)
    is_visible: bool = Field(default=True, nullable=False)
    orden: int = Field(default=0, sa_type=SmallInteger, nullable=False)
