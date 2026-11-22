from uuid import UUID

from sqlalchemy import Index, SmallInteger, String, Text, text
from sqlmodel import Field

from app.core.base_model import BaseModel, enum_type
from app.shared.enums import RedSocial


class TarjetaSocial(BaseModel, table=True):
    __tablename__ = "tarjeta_social"
    __table_args__ = (
        # Una cuenta por red en cada tarjeta.
        Index(
            "uq_tarjeta_social_tarjeta_id_red_not_deleted",
            "tarjeta_id",
            "red",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    tarjeta_id: UUID = Field(foreign_key="tarjeta.id", nullable=False)
    red: RedSocial = Field(sa_type=enum_type(RedSocial, "red_social"), nullable=False)
    url: str = Field(sa_type=Text, nullable=False)
    username: str | None = Field(default=None, sa_type=String(100), nullable=True)
    is_visible: bool = Field(default=True, nullable=False)
    orden: int = Field(default=0, sa_type=SmallInteger, nullable=False)
