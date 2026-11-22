from uuid import UUID

from sqlalchemy import SmallInteger, String, Text
from sqlmodel import Field

from app.core.base_model import BaseModel


class TarjetaFaq(BaseModel, table=True):
    __tablename__ = "tarjeta_faq"

    tarjeta_id: UUID = Field(foreign_key="tarjeta.id", nullable=False, index=True)
    pregunta: str = Field(sa_type=String(300), nullable=False)
    respuesta: str = Field(sa_type=Text, nullable=False)
    is_visible: bool = Field(default=True, nullable=False)
    orden: int = Field(default=0, sa_type=SmallInteger, nullable=False)
