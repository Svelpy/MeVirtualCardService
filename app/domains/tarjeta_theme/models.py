from uuid import UUID

from sqlalchemy import CHAR, CheckConstraint, SmallInteger
from sqlmodel import Field

from app.core.base_model import BaseModel, enum_type
from app.shared.enums import FormaIcono, PosicionFab, PresetTheme


class TarjetaTheme(BaseModel, table=True):
    """
    Extensión 1:1 de la tarjeta: su id es el id de la tarjeta (AGENTS.md §18).
    Todos los color_* son #RRGGBB; al crearla toman los valores del preset.
    """

    __tablename__ = "tarjeta_theme"
    __table_args__ = (
        CheckConstraint("overlay_opacidad BETWEEN 0 AND 100", name="overlay_opacidad_valida"),
    )

    id: UUID = Field(foreign_key="tarjeta.id", primary_key=True)
    # NULL = personalizado: algún color se cambió a mano.
    preset: PresetTheme | None = Field(
        default=None,
        sa_type=enum_type(PresetTheme, "preset_theme"),
        nullable=True,
    )
    # Id del par de fuentes en TIPOGRAFIAS_TARJETA del frontend.
    tipografia: int = Field(default=1, sa_type=SmallInteger, nullable=False)
    color_fondo: str = Field(sa_type=CHAR(7), nullable=False)
    color_superficie: str = Field(sa_type=CHAR(7), nullable=False)
    color_borde: str = Field(sa_type=CHAR(7), nullable=False)
    color_titulo: str = Field(sa_type=CHAR(7), nullable=False)
    color_texto: str = Field(sa_type=CHAR(7), nullable=False)
    color_texto_secundario: str = Field(sa_type=CHAR(7), nullable=False)
    color_primario: str = Field(sa_type=CHAR(7), nullable=False)
    color_texto_sobre_primario: str = Field(sa_type=CHAR(7), nullable=False)
    color_secundario: str = Field(sa_type=CHAR(7), nullable=False)
    color_texto_sobre_secundario: str = Field(sa_type=CHAR(7), nullable=False)
    color_overlay_portada: str = Field(default="#000000", sa_type=CHAR(7), nullable=False)
    overlay_opacidad: int = Field(default=40, sa_type=SmallInteger, nullable=False)
    color_precio: str = Field(sa_type=CHAR(7), nullable=False)
    color_destacado: str = Field(sa_type=CHAR(7), nullable=False)
    color_texto_sobre_destacado: str = Field(sa_type=CHAR(7), nullable=False)
    color_icono: str = Field(sa_type=CHAR(7), nullable=False)
    color_fondo_icono: str = Field(sa_type=CHAR(7), nullable=False)
    icono_forma: FormaIcono = Field(
        default=FormaIcono.CIRCULO,
        sa_type=enum_type(FormaIcono, "forma_icono"),
        nullable=False,
    )
    color_icono_social: str = Field(sa_type=CHAR(7), nullable=False)
    color_fondo_icono_social: str = Field(sa_type=CHAR(7), nullable=False)
    color_fab_fondo: str = Field(sa_type=CHAR(7), nullable=False)
    color_fab_icono: str = Field(sa_type=CHAR(7), nullable=False)
    fab_posicion: PosicionFab = Field(
        default=PosicionFab.DERECHA,
        sa_type=enum_type(PosicionFab, "posicion_fab"),
        nullable=False,
    )
