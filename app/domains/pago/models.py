from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, DateTime, Index, Numeric, String, Text
from sqlmodel import Field, Relationship

from app.core.base_model import BaseModel, enum_type
from app.shared.enums import MetodoPago

if TYPE_CHECKING:
    from app.domains.plan.models import Plan
    from app.domains.usuario.models import Usuario


class Pago(BaseModel, table=True):
    """
    Registro (kardex, AGENTS.md §19): solo INSERT. Un trigger de la migración
    rechaza UPDATE y DELETE. Anular es insertar un reverso con reverses_id.
    Sin filas eliminadas, sus índices únicos no son parciales.
    """

    __tablename__ = "pago"
    __table_args__ = (
        Index("uq_pago_reverses_id", "reverses_id", unique=True),
        Index("uq_pago_idempotency_key", "idempotency_key", unique=True),
        CheckConstraint("periodo_fin > periodo_inicio", name="periodo_valido"),
        # Un pago es positivo; su reverso, negativo.
        CheckConstraint(
            "(reverses_id IS NULL AND monto >= 0) OR (reverses_id IS NOT NULL AND monto <= 0)",
            name="signo_del_monto",
        ),
    )

    user_id: UUID = Field(foreign_key="usuario.id", nullable=False, index=True)
    plan_id: UUID = Field(foreign_key="plan.id", nullable=False, index=True)
    monto: Decimal = Field(sa_type=Numeric(12, 2), nullable=False)
    moneda: str = Field(sa_type=CHAR(3), nullable=False)
    metodo: MetodoPago = Field(sa_type=enum_type(MetodoPago, "metodo_pago"), nullable=False)
    referencia_externa: str | None = Field(default=None, sa_type=String(100), nullable=True)
    comprobante_url: str | None = Field(default=None, sa_type=Text, nullable=True)
    periodo_inicio: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    periodo_fin: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    reverses_id: UUID | None = Field(default=None, foreign_key="pago.id", nullable=True)
    idempotency_key: str = Field(sa_type=String(64), nullable=False)

    user: "Usuario" = Relationship(sa_relationship_kwargs={"lazy": "raise"})
    plan: "Plan" = Relationship(sa_relationship_kwargs={"lazy": "raise"})
