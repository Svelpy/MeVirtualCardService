from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Numeric, SmallInteger, String, Text
from sqlmodel import Field, Relationship

from app.core.base_model import BaseModel

if TYPE_CHECKING:
    from app.domains.ubicacion_horario.models import UbicacionHorario


class TarjetaUbicacion(BaseModel, table=True):
    __tablename__ = "tarjeta_ubicacion"
    __table_args__ = (
        CheckConstraint("(lat IS NULL) = (lng IS NULL)", name="coordenadas_juntas"),
        CheckConstraint("lat BETWEEN -90 AND 90", name="latitud_valida"),
        CheckConstraint("lng BETWEEN -180 AND 180", name="longitud_valida"),
    )

    tarjeta_id: UUID = Field(foreign_key="tarjeta.id", nullable=False, index=True)
    nombre: str | None = Field(default=None, sa_type=String(150), nullable=True)
    direccion: str = Field(sa_type=String(255), nullable=False)
    ciudad: str | None = Field(default=None, sa_type=String(100), nullable=True)
    departamento: str | None = Field(default=None, sa_type=String(100), nullable=True)
    pais: str | None = Field(default=None, sa_type=String(100), nullable=True)
    maps_url: str | None = Field(default=None, sa_type=Text, nullable=True)
    lat: Decimal | None = Field(default=None, sa_type=Numeric(9, 6), nullable=True)
    lng: Decimal | None = Field(default=None, sa_type=Numeric(9, 6), nullable=True)
    is_visible: bool = Field(default=True, nullable=False)
    orden: int = Field(default=0, sa_type=SmallInteger, nullable=False)

    horarios: list["UbicacionHorario"] = Relationship(
        sa_relationship_kwargs={
            "lazy": "raise",
            "order_by": "[UbicacionHorario.dia_semana, UbicacionHorario.hora_inicio]",
        }
    )
