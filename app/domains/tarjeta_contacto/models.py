from uuid import UUID

from sqlalchemy import CheckConstraint, Index, SmallInteger, String, text
from sqlmodel import Field

from app.core.base_model import BaseModel, enum_type
from app.shared.enums import TipoContacto


class TarjetaContacto(BaseModel, table=True):
    __tablename__ = "tarjeta_contacto"
    __table_args__ = (
        # Un solo contacto principal por tipo en cada tarjeta.
        Index(
            "uq_tarjeta_contacto_principal_not_deleted",
            "tarjeta_id",
            "tipo",
            unique=True,
            postgresql_where=text("is_primary AND is_deleted = false"),
        ),
        CheckConstraint("NOT is_wpp OR tipo = 'phone'", name="wpp_solo_en_telefono"),
    )

    tarjeta_id: UUID = Field(foreign_key="tarjeta.id", nullable=False, index=True)
    tipo: TipoContacto = Field(sa_type=enum_type(TipoContacto, "tipo_contacto"), nullable=False)
    valor: str = Field(sa_type=String(255), nullable=False)  # número, correo o URL, según tipo
    etiqueta: str | None = Field(default=None, sa_type=String(60), nullable=True)
    is_wpp: bool = Field(default=False, nullable=False)
    is_primary: bool = Field(default=False, nullable=False)
    is_visible: bool = Field(default=True, nullable=False)
    orden: int = Field(default=0, sa_type=SmallInteger, nullable=False)
