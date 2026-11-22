from decimal import Decimal

from sqlalchemy import CHAR, CheckConstraint, Index, Numeric, SmallInteger, String, text
from sqlmodel import Field

from app.core.base_model import BaseModel


class Plan(BaseModel, table=True):
    """Filas fijas: free, pro y business se siembran en la migración inicial."""

    __tablename__ = "plan"
    __table_args__ = (
        Index(
            "uq_plan_codigo_not_deleted",
            "codigo",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        CheckConstraint("precio >= 0", name="precio_no_negativo"),
        CheckConstraint("duracion_dias > 0", name="duracion_positiva"),
    )

    codigo: str = Field(sa_type=String(10), nullable=False)
    nombre: str = Field(sa_type=String(60), nullable=False)
    precio: Decimal = Field(sa_type=Numeric(12, 2), nullable=False)
    moneda: str = Field(default="USD", sa_type=CHAR(3), nullable=False)
    duracion_dias: int = Field(sa_type=SmallInteger, nullable=False)
    is_visible: bool = Field(default=True, nullable=False)
