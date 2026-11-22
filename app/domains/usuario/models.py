from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Index, String, Text, text
from sqlmodel import Field, Relationship

from app.core.base_model import BaseModel, enum_type
from app.shared.enums import Role

if TYPE_CHECKING:
    from app.domains.plan.models import Plan


class Usuario(BaseModel, table=True):
    __tablename__ = "usuario"
    __table_args__ = (
        Index(
            "uq_usuario_email_not_deleted",
            "email",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    email: str = Field(sa_type=String(255), nullable=False)
    password_hash: str = Field(sa_type=Text, nullable=False)
    rol: Role = Field(default=Role.USER, sa_type=enum_type(Role, "rol_usuario"), nullable=False)
    plan_id: UUID = Field(foreign_key="plan.id", nullable=False, index=True)
    # Estado del plan: solo cambia al registrar un pago.
    plan_vence_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    # Estado: solo cambia con los endpoints de acción dar de baja / reactivar.
    is_active: bool = Field(default=True, nullable=False)
    email_verified_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )

    plan: "Plan" = Relationship(sa_relationship_kwargs={"lazy": "raise"})
