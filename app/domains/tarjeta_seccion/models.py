from uuid import UUID

from sqlalchemy import Index, SmallInteger, String, text
from sqlmodel import Field

from app.core.base_model import BaseModel, enum_type
from app.shared.enums import ClaveSeccion


class TarjetaSeccion(BaseModel, table=True):
    """
    Hija embebida fija de la tarjeta: el service crea las 8 junto con la
    tarjeta; por la API solo se actualizan, nunca se crean ni se eliminan.
    """

    __tablename__ = "tarjeta_seccion"
    __table_args__ = (
        Index(
            "uq_tarjeta_seccion_tarjeta_id_clave_not_deleted",
            "tarjeta_id",
            "clave",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    tarjeta_id: UUID = Field(foreign_key="tarjeta.id", nullable=False)
    clave: ClaveSeccion = Field(sa_type=enum_type(ClaveSeccion, "clave_seccion"), nullable=False)
    titulo: str | None = Field(default=None, sa_type=String(80), nullable=True)
    is_visible: bool = Field(default=True, nullable=False)
    orden: int = Field(default=0, sa_type=SmallInteger, nullable=False)
