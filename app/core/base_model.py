from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


# Nombres predecibles para constraints e índices sin nombre explícito, para que
# una migration posterior pueda eliminarlos (AGENTS.md §8).
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def enum_type(enum_class: type[Enum], name: str) -> SAEnum:
    """
    Tipo ENUM de PostgreSQL con el nombre de database.md. Guarda el valor de
    cada miembro ("user"), no su nombre ("USER"), que es lo que SQLAlchemy
    haría por defecto.
    """
    return SAEnum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )


class BaseModel(SQLModel):
    """Modelo base abstracto con campos comunes de auditoría."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now,sa_type=DateTime(timezone=True),nullable=False)
    created_by: UUID | None = Field(default=None, nullable=True)
    updated_at: datetime = Field(default_factory=utc_now,sa_type=DateTime(timezone=True),nullable=False)
    updated_by: UUID | None = Field(default=None, nullable=True)
    is_deleted: bool = Field(default=False, nullable=False, index=True)
    deleted_at: datetime | None = Field(default=None,sa_type=DateTime(timezone=True),nullable=True)
    deleted_by: UUID | None = Field(default=None, nullable=True)
