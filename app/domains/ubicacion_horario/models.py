from datetime import time
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, SmallInteger, Time, text
from sqlmodel import Field

from app.core.base_model import BaseModel


class UbicacionHorario(BaseModel, table=True):
    """
    Tramo horario de una ubicación. No admite tramos que crucen la medianoche;
    el service rechaza los que se solapan en un mismo día.
    """

    __tablename__ = "ubicacion_horario"
    __table_args__ = (
        Index(
            # (ubicacion_id, dia_semana, hora_inicio); el nombre largo pasaría de 63 caracteres.
            "uq_ubicacion_horario_tramo_not_deleted",
            "ubicacion_id",
            "dia_semana",
            "hora_inicio",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        CheckConstraint("dia_semana BETWEEN 1 AND 7", name="dia_semana_valido"),
        CheckConstraint("hora_fin > hora_inicio", name="tramo_valido"),
    )

    ubicacion_id: UUID = Field(foreign_key="tarjeta_ubicacion.id", nullable=False)
    dia_semana: int = Field(sa_type=SmallInteger, nullable=False)  # 1 lunes a 7 domingo
    hora_inicio: time = Field(sa_type=Time, nullable=False)
    hora_fin: time = Field(sa_type=Time, nullable=False)
