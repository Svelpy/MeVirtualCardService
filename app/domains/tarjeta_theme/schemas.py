from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.shared.enums import FormaIcono, PosicionFab, PresetTheme
from app.shared.schemas.base import AUDIT_EXAMPLE, SMALLINT_MAX, AuditMixin, SchemaBase, reject_null
from app.shared.services.validators import validator_hex_color, validator_integer, validator_positive_integer


# Campos de color, todos #RRGGBB.
COLOR_FIELDS = (
    "color_fondo",
    "color_superficie",
    "color_borde",
    "color_titulo",
    "color_texto",
    "color_texto_secundario",
    "color_primario",
    "color_texto_sobre_primario",
    "color_secundario",
    "color_texto_sobre_secundario",
    "color_overlay_portada",
    "color_precio",
    "color_destacado",
    "color_texto_sobre_destacado",
    "color_icono",
    "color_fondo_icono",
    "color_icono_social",
    "color_fondo_icono_social",
    "color_fab_fondo",
    "color_fab_icono",
)

# Campos que define un preset, en el orden de las columnas: los colores más la
# capa de la portada, la forma de los íconos y la posición del botón flotante.
PRESET_FIELDS = (
    "color_fondo",
    "color_superficie",
    "color_borde",
    "color_titulo",
    "color_texto",
    "color_texto_secundario",
    "color_primario",
    "color_texto_sobre_primario",
    "color_secundario",
    "color_texto_sobre_secundario",
    "color_overlay_portada",
    "overlay_opacidad",
    "color_precio",
    "color_destacado",
    "color_texto_sobre_destacado",
    "color_icono",
    "color_fondo_icono",
    "icono_forma",
    "color_icono_social",
    "color_fondo_icono_social",
    "color_fab_fondo",
    "color_fab_icono",
    "fab_posicion",
)

# Valores de cada preset, definidos por el frontend (TEMAS_TARJETA). Crear el
# theme o aplicar un preset copia estos valores; cambiar después cualquiera de
# ellos a mano deja preset = NULL (personalizado). La tipografía no es parte del
# preset: al crear es 1 y aplicar un preset no la cambia.
THEME_PRESETS: dict[PresetTheme, dict[str, str | int | FormaIcono | PosicionFab]] = {
    PresetTheme.CLARO: {
        "color_fondo": "#FFFFFF",
        "color_superficie": "#F6F7F9",
        "color_borde": "#E3E6EB",
        "color_titulo": "#111827",
        "color_texto": "#374151",
        "color_texto_secundario": "#6B7280",
        "color_primario": "#2563EB",
        "color_texto_sobre_primario": "#FFFFFF",
        "color_secundario": "#E0E7FF",
        "color_texto_sobre_secundario": "#1E3A8A",
        "color_overlay_portada": "#000000",
        "overlay_opacidad": 40,
        "color_precio": "#047857",
        "color_destacado": "#F59E0B",
        "color_texto_sobre_destacado": "#111827",
        "color_icono": "#2563EB",
        "color_fondo_icono": "#EFF6FF",
        "icono_forma": FormaIcono.CIRCULO,
        "color_icono_social": "#374151",
        "color_fondo_icono_social": "#F3F4F6",
        "color_fab_fondo": "#2563EB",
        "color_fab_icono": "#FFFFFF",
        "fab_posicion": PosicionFab.DERECHA,
    },
    PresetTheme.OSCURO: {
        "color_fondo": "#111318",
        "color_superficie": "#1B1E25",
        "color_borde": "#2C313C",
        "color_titulo": "#F9FAFB",
        "color_texto": "#D1D5DB",
        "color_texto_secundario": "#9CA3AF",
        "color_primario": "#60A5FA",
        "color_texto_sobre_primario": "#0B1220",
        "color_secundario": "#273041",
        "color_texto_sobre_secundario": "#E5E7EB",
        "color_overlay_portada": "#000000",
        "overlay_opacidad": 55,
        "color_precio": "#34D399",
        "color_destacado": "#FBBF24",
        "color_texto_sobre_destacado": "#111827",
        "color_icono": "#93C5FD",
        "color_fondo_icono": "#1E293B",
        "icono_forma": FormaIcono.REDONDEADO,
        "color_icono_social": "#E5E7EB",
        "color_fondo_icono_social": "#273041",
        "color_fab_fondo": "#60A5FA",
        "color_fab_icono": "#0B1220",
        "fab_posicion": PosicionFab.DERECHA,
    },
    PresetTheme.ELEGANTE: {
        "color_fondo": "#FAF8F5",
        "color_superficie": "#FFFFFF",
        "color_borde": "#E7E1D8",
        "color_titulo": "#1C1917",
        "color_texto": "#44403C",
        "color_texto_secundario": "#6F6862",
        "color_primario": "#1C1917",
        "color_texto_sobre_primario": "#F5E6C8",
        "color_secundario": "#F1EADF",
        "color_texto_sobre_secundario": "#57452A",
        "color_overlay_portada": "#1C1917",
        "overlay_opacidad": 45,
        "color_precio": "#7A5F2E",
        "color_destacado": "#C9A86A",
        "color_texto_sobre_destacado": "#1C1917",
        "color_icono": "#7A5F2E",
        "color_fondo_icono": "#F5EFE4",
        "icono_forma": FormaIcono.CUADRADO,
        "color_icono_social": "#1C1917",
        "color_fondo_icono_social": "#F1EADF",
        "color_fab_fondo": "#1C1917",
        "color_fab_icono": "#F5E6C8",
        "fab_posicion": PosicionFab.DERECHA,
    },
    PresetTheme.SALUD: {
        "color_fondo": "#F7FBFA",
        "color_superficie": "#FFFFFF",
        "color_borde": "#D5ECE7",
        "color_titulo": "#0F3D38",
        "color_texto": "#334155",
        "color_texto_secundario": "#5B6B7F",
        "color_primario": "#0F766E",
        "color_texto_sobre_primario": "#FFFFFF",
        "color_secundario": "#CCFBF1",
        "color_texto_sobre_secundario": "#115E59",
        "color_overlay_portada": "#0F3D38",
        "overlay_opacidad": 35,
        "color_precio": "#0F766E",
        "color_destacado": "#F472B6",
        "color_texto_sobre_destacado": "#3B0A24",
        "color_icono": "#0F766E",
        "color_fondo_icono": "#CCFBF1",
        "icono_forma": FormaIcono.CIRCULO,
        "color_icono_social": "#0F766E",
        "color_fondo_icono_social": "#E6F6F3",
        "color_fab_fondo": "#0F766E",
        "color_fab_icono": "#FFFFFF",
        "fab_posicion": PosicionFab.DERECHA,
    },
    PresetTheme.CORPORATIVO: {
        "color_fondo": "#F8FAFC",
        "color_superficie": "#FFFFFF",
        "color_borde": "#E2E8F0",
        "color_titulo": "#0F172A",
        "color_texto": "#334155",
        "color_texto_secundario": "#5B6B7F",
        "color_primario": "#1E3A8A",
        "color_texto_sobre_primario": "#FFFFFF",
        "color_secundario": "#E2E8F0",
        "color_texto_sobre_secundario": "#1E293B",
        "color_overlay_portada": "#0F172A",
        "overlay_opacidad": 50,
        "color_precio": "#1E3A8A",
        "color_destacado": "#FACC15",
        "color_texto_sobre_destacado": "#0F172A",
        "color_icono": "#1E3A8A",
        "color_fondo_icono": "#E0E7FF",
        "icono_forma": FormaIcono.REDONDEADO,
        "color_icono_social": "#1E293B",
        "color_fondo_icono_social": "#F1F5F9",
        "color_fab_fondo": "#1E3A8A",
        "color_fab_icono": "#FFFFFF",
        "fab_posicion": PosicionFab.DERECHA,
    },
    PresetTheme.CALIDO: {
        "color_fondo": "#FFF9F2",
        "color_superficie": "#FFFFFF",
        "color_borde": "#F1DFCC",
        "color_titulo": "#3A1A0B",
        "color_texto": "#4A3426",
        "color_texto_secundario": "#7A5A44",
        "color_primario": "#B42318",
        "color_texto_sobre_primario": "#FFFFFF",
        "color_secundario": "#FDE8D0",
        "color_texto_sobre_secundario": "#7A2E0E",
        "color_overlay_portada": "#3A1A0B",
        "overlay_opacidad": 45,
        "color_precio": "#9A3412",
        "color_destacado": "#F4B740",
        "color_texto_sobre_destacado": "#3A1A0B",
        "color_icono": "#B42318",
        "color_fondo_icono": "#FDECE7",
        "icono_forma": FormaIcono.REDONDEADO,
        "color_icono_social": "#3A1A0B",
        "color_fondo_icono_social": "#F7EBDD",
        "color_fab_fondo": "#B42318",
        "color_fab_icono": "#FFFFFF",
        "fab_posicion": PosicionFab.DERECHA,
    },
    PresetTheme.NATURAL: {
        "color_fondo": "#F6F7F2",
        "color_superficie": "#FFFFFF",
        "color_borde": "#DDE3D1",
        "color_titulo": "#1F2A1C",
        "color_texto": "#39463A",
        "color_texto_secundario": "#5E6B5C",
        "color_primario": "#4D6B3C",
        "color_texto_sobre_primario": "#FFFFFF",
        "color_secundario": "#E4ECD9",
        "color_texto_sobre_secundario": "#2F4424",
        "color_overlay_portada": "#1F2A1C",
        "overlay_opacidad": 40,
        "color_precio": "#3F5A30",
        "color_destacado": "#E9C46A",
        "color_texto_sobre_destacado": "#1F2A1C",
        "color_icono": "#4D6B3C",
        "color_fondo_icono": "#E8EFDF",
        "icono_forma": FormaIcono.CIRCULO,
        "color_icono_social": "#2F4424",
        "color_fondo_icono_social": "#EDF1E6",
        "color_fab_fondo": "#4D6B3C",
        "color_fab_icono": "#FFFFFF",
        "fab_posicion": PosicionFab.DERECHA,
    },
    PresetTheme.BELLEZA: {
        "color_fondo": "#FFF7F8",
        "color_superficie": "#FFFFFF",
        "color_borde": "#F3D9DF",
        "color_titulo": "#3B0A1E",
        "color_texto": "#4F2A36",
        "color_texto_secundario": "#7D5260",
        "color_primario": "#9D174D",
        "color_texto_sobre_primario": "#FFFFFF",
        "color_secundario": "#FCE7EF",
        "color_texto_sobre_secundario": "#831843",
        "color_overlay_portada": "#3B0A1E",
        "overlay_opacidad": 35,
        "color_precio": "#9D174D",
        "color_destacado": "#F9A8D4",
        "color_texto_sobre_destacado": "#3B0A1E",
        "color_icono": "#9D174D",
        "color_fondo_icono": "#FCE7EF",
        "icono_forma": FormaIcono.CIRCULO,
        "color_icono_social": "#831843",
        "color_fondo_icono_social": "#FDF0F5",
        "color_fab_fondo": "#9D174D",
        "color_fab_icono": "#FFFFFF",
        "fab_posicion": PosicionFab.DERECHA,
    },
    PresetTheme.CREATIVO: {
        "color_fondo": "#F7F5FF",
        "color_superficie": "#FFFFFF",
        "color_borde": "#E2DDF7",
        "color_titulo": "#1A1033",
        "color_texto": "#3A3350",
        "color_texto_secundario": "#5F5878",
        "color_primario": "#5B21B6",
        "color_texto_sobre_primario": "#FFFFFF",
        "color_secundario": "#EDE9FE",
        "color_texto_sobre_secundario": "#4C1D95",
        "color_overlay_portada": "#1A1033",
        "overlay_opacidad": 45,
        "color_precio": "#5B21B6",
        "color_destacado": "#FB923C",
        "color_texto_sobre_destacado": "#1A1033",
        "color_icono": "#5B21B6",
        "color_fondo_icono": "#EDE9FE",
        "icono_forma": FormaIcono.CUADRADO,
        "color_icono_social": "#1A1033",
        "color_fondo_icono_social": "#F1EEFB",
        "color_fab_fondo": "#5B21B6",
        "color_fab_icono": "#FFFFFF",
        "fab_posicion": PosicionFab.DERECHA,
    },
    PresetTheme.ENERGIA: {
        "color_fondo": "#0F1115",
        "color_superficie": "#1A1D23",
        "color_borde": "#2B3039",
        "color_titulo": "#F8FAFC",
        "color_texto": "#D4D8DE",
        "color_texto_secundario": "#A0A7B4",
        "color_primario": "#FACC15",
        "color_texto_sobre_primario": "#0F1115",
        "color_secundario": "#262A31",
        "color_texto_sobre_secundario": "#F1F5F9",
        "color_overlay_portada": "#000000",
        "overlay_opacidad": 55,
        "color_precio": "#FDE047",
        "color_destacado": "#F97316",
        "color_texto_sobre_destacado": "#0F1115",
        "color_icono": "#FACC15",
        "color_fondo_icono": "#262A31",
        "icono_forma": FormaIcono.CUADRADO,
        "color_icono_social": "#F1F5F9",
        "color_fondo_icono_social": "#262A31",
        "color_fab_fondo": "#FACC15",
        "color_fab_icono": "#0F1115",
        "fab_posicion": PosicionFab.DERECHA,
    },
}

# Apariencia editable, en el orden de las columnas: la del preset claro.
_APARIENCIA_EXAMPLE = {
    "tipografia": 1,
    **{
        field: value.value if isinstance(value, FormaIcono | PosicionFab) else value
        for field, value in THEME_PRESETS[PresetTheme.CLARO].items()
    },
}
TARJETA_THEME_RESPONSE_EXAMPLE = {
    "id": "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b",
    "preset": "claro",
    **_APARIENCIA_EXAMPLE,
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
TARJETA_THEME_CREATE_EXAMPLE = {"preset": "salud"}
TARJETA_THEME_PUBLIC_EXAMPLE = _APARIENCIA_EXAMPLE


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaThemeCreate(SchemaBase):
    """
    Extensión 1:1: se crea junto con la tarjeta y con su mismo id. Solo se elige
    el preset: el service copia sus valores (THEME_PRESETS) y la tipografía es 1.
    """

    preset: PresetTheme = PresetTheme.CLARO

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_THEME_CREATE_EXAMPLE})


class TarjetaThemeUpdate(SchemaBase):
    """
    PATCH /tarjeta-themes/{id}. Cambiar a mano un campo del preset (PRESET_FIELDS)
    deja preset = NULL (personalizado); la tipografía no. El preset se aplica con
    POST /{id}/aplicar-preset.
    """

    tipografia: int = Field(default=None, le=SMALLINT_MAX)
    color_fondo: str = Field(default=None, max_length=7)
    color_superficie: str = Field(default=None, max_length=7)
    color_borde: str = Field(default=None, max_length=7)
    color_titulo: str = Field(default=None, max_length=7)
    color_texto: str = Field(default=None, max_length=7)
    color_texto_secundario: str = Field(default=None, max_length=7)
    color_primario: str = Field(default=None, max_length=7)
    color_texto_sobre_primario: str = Field(default=None, max_length=7)
    color_secundario: str = Field(default=None, max_length=7)
    color_texto_sobre_secundario: str = Field(default=None, max_length=7)
    color_overlay_portada: str = Field(default=None, max_length=7)
    overlay_opacidad: int = Field(default=None, ge=0, le=100)
    color_precio: str = Field(default=None, max_length=7)
    color_destacado: str = Field(default=None, max_length=7)
    color_texto_sobre_destacado: str = Field(default=None, max_length=7)
    color_icono: str = Field(default=None, max_length=7)
    color_fondo_icono: str = Field(default=None, max_length=7)
    icono_forma: FormaIcono = Field(default=None)
    color_icono_social: str = Field(default=None, max_length=7)
    color_fondo_icono_social: str = Field(default=None, max_length=7)
    color_fab_fondo: str = Field(default=None, max_length=7)
    color_fab_icono: str = Field(default=None, max_length=7)
    fab_posicion: PosicionFab = Field(default=None)

    @field_validator("tipografia", mode="before")
    @classmethod
    def validate_tipografia(cls, value: object) -> int:
        return validator_positive_integer(reject_null(value))

    @field_validator(*COLOR_FIELDS, mode="before")
    @classmethod
    def validate_color(cls, value: object) -> str:
        return validator_hex_color(reject_null(value))

    @field_validator("overlay_opacidad", mode="before")
    @classmethod
    def validate_overlay_opacidad(cls, value: object) -> int:
        return validator_integer(reject_null(value))

    model_config = ConfigDict(json_schema_extra={"example": _APARIENCIA_EXAMPLE})


class TarjetaThemeAplicarPreset(SchemaBase):
    """POST /tarjeta-themes/{id}/aplicar-preset: copia los valores del preset; la tipografía no cambia."""

    preset: PresetTheme

    model_config = ConfigDict(json_schema_extra={"example": {"preset": "oscuro"}})


class TarjetaThemeResponse(SchemaBase):
    id: UUID
    preset: PresetTheme | None
    tipografia: int
    color_fondo: str
    color_superficie: str
    color_borde: str
    color_titulo: str
    color_texto: str
    color_texto_secundario: str
    color_primario: str
    color_texto_sobre_primario: str
    color_secundario: str
    color_texto_sobre_secundario: str
    color_overlay_portada: str
    overlay_opacidad: int
    color_precio: str
    color_destacado: str
    color_texto_sobre_destacado: str
    color_icono: str
    color_fondo_icono: str
    icono_forma: FormaIcono
    color_icono_social: str
    color_fondo_icono_social: str
    color_fab_fondo: str
    color_fab_icono: str
    fab_posicion: PosicionFab
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_THEME_RESPONSE_EXAMPLE})


class TarjetaThemeResponseAudit(AuditMixin, TarjetaThemeResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_THEME_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class TarjetaThemePublic(SchemaBase):
    tipografia: int
    color_fondo: str
    color_superficie: str
    color_borde: str
    color_titulo: str
    color_texto: str
    color_texto_secundario: str
    color_primario: str
    color_texto_sobre_primario: str
    color_secundario: str
    color_texto_sobre_secundario: str
    color_overlay_portada: str
    overlay_opacidad: int
    color_precio: str
    color_destacado: str
    color_texto_sobre_destacado: str
    color_icono: str
    color_fondo_icono: str
    icono_forma: FormaIcono
    color_icono_social: str
    color_fondo_icono_social: str
    color_fab_fondo: str
    color_fab_icono: str
    fab_posicion: PosicionFab

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_THEME_PUBLIC_EXAMPLE})
