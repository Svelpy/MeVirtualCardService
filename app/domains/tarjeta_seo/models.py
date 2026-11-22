from uuid import UUID

from sqlalchemy import String, Text
from sqlmodel import Field

from app.core.base_model import BaseModel


class TarjetaSeo(BaseModel, table=True):
    """Extensión 1:1 de la tarjeta: su id es el id de la tarjeta (AGENTS.md §18)."""

    __tablename__ = "tarjeta_seo"

    id: UUID = Field(foreign_key="tarjeta.id", primary_key=True)
    meta_title: str | None = Field(default=None, sa_type=String(70), nullable=True)  # NULL = se genera
    meta_description: str | None = Field(default=None, sa_type=String(160), nullable=True)  # NULL = se genera
    og_image_url: str | None = Field(default=None, sa_type=Text, nullable=True)  # NULL = profile_url
    robots_index: bool = Field(default=True, nullable=False)
