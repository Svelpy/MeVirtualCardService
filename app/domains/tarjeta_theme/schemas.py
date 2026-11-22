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

# Colores de cada preset, en el orden de COLOR_FIELDS. Aplicar un preset copia
# estos valores; cambiar después un color a mano deja preset = NULL.
THEME_PRESETS: dict[PresetTheme, dict[str, str]] = {
    PresetTheme.CLARO: {
        "color_fondo": "#FFFFFF",
        "color_superficie": "#F5F7FA",
        "color_borde": "#E2E8F0",
        "color_titulo": "#1A202C",
        "color_texto": "#2D3748",
        "color_texto_secundario": "#718096",
        "color_primario": "#2B6CB0",
        "color_texto_sobre_primario": "#FFFFFF",
        "color_secundario": "#EDF2F7",
        "color_texto_sobre_secundario": "#2D3748",
        "color_overlay_portada": "#000000",
        "color_precio": "#2F855A",
        "color_destacado": "#D69E2E",
        "color_texto_sobre_destacado": "#FFFFFF",
        "color_icono": "#2B6CB0",
        "color_fondo_icono": "#EBF8FF",
        "color_icono_social": "#FFFFFF",
        "color_fondo_icono_social": "#2B6CB0",
        "color_fab_fondo": "#25D366",
        "color_fab_icono": "#FFFFFF",
    },
    PresetTheme.OSCURO: {
        "color_fondo": "#121212",
        "color_superficie": "#1E1E1E",
        "color_borde": "#2C2C2C",
        "color_titulo": "#F5F5F5",
        "color_texto": "#E0E0E0",
        "color_texto_secundario": "#A0A0A0",
        "color_primario": "#4F9CF9",
        "color_texto_sobre_primario": "#0B1220",
        "color_secundario": "#2A2A2A",
        "color_texto_sobre_secundario": "#E0E0E0",
        "color_overlay_portada": "#000000",
        "color_precio": "#4ADE80",
        "color_destacado": "#FBBF24",
        "color_texto_sobre_destacado": "#1A1A1A",
        "color_icono": "#4F9CF9",
        "color_fondo_icono": "#1C2A3D",
        "color_icono_social": "#121212",
        "color_fondo_icono_social": "#4F9CF9",
        "color_fab_fondo": "#25D366",
        "color_fab_icono": "#FFFFFF",
    },
    PresetTheme.ELEGANTE: {
        "color_fondo": "#FAF8F5",
        "color_superficie": "#FFFFFF",
        "color_borde": "#E7E1D7",
        "color_titulo": "#1F1B16",
        "color_texto": "#3D3730",
        "color_texto_secundario": "#8A8175",
        "color_primario": "#1F1B16",
        "color_texto_sobre_primario": "#F5E9D3",
        "color_secundario": "#F1EBE1",
        "color_texto_sobre_secundario": "#3D3730",
        "color_overlay_portada": "#1F1B16",
        "color_precio": "#8C6A2F",
        "color_destacado": "#B8924A",
        "color_texto_sobre_destacado": "#FFFFFF",
        "color_icono": "#B8924A",
        "color_fondo_icono": "#F5EEDF",
        "color_icono_social": "#F5E9D3",
        "color_fondo_icono_social": "#1F1B16",
        "color_fab_fondo": "#1F1B16",
        "color_fab_icono": "#F5E9D3",
    },
    PresetTheme.SALUD: {
        "color_fondo": "#F7FBFB",
        "color_superficie": "#FFFFFF",
        "color_borde": "#D6EAEA",
        "color_titulo": "#0F3D3E",
        "color_texto": "#234E52",
        "color_texto_secundario": "#5F7F81",
        "color_primario": "#0E9F9A",
        "color_texto_sobre_primario": "#FFFFFF",
        "color_secundario": "#E3F4F3",
        "color_texto_sobre_secundario": "#0F3D3E",
        "color_overlay_portada": "#0F3D3E",
        "color_precio": "#0E9F9A",
        "color_destacado": "#F59E0B",
        "color_texto_sobre_destacado": "#FFFFFF",
        "color_icono": "#0E9F9A",
        "color_fondo_icono": "#E3F4F3",
        "color_icono_social": "#FFFFFF",
        "color_fondo_icono_social": "#0E9F9A",
        "color_fab_fondo": "#25D366",
        "color_fab_icono": "#FFFFFF",
    },
    PresetTheme.CORPORATIVO: {
        "color_fondo": "#FFFFFF",
        "color_superficie": "#F3F4F6",
        "color_borde": "#D1D5DB",
        "color_titulo": "#111827",
        "color_texto": "#1F2937",
        "color_texto_secundario": "#6B7280",
        "color_primario": "#1E3A8A",
        "color_texto_sobre_primario": "#FFFFFF",
        "color_secundario": "#E5E7EB",
        "color_texto_sobre_secundario": "#1F2937",
        "color_overlay_portada": "#111827",
        "color_precio": "#047857",
        "color_destacado": "#DC2626",
        "color_texto_sobre_destacado": "#FFFFFF",
        "color_icono": "#1E3A8A",
        "color_fondo_icono": "#DBEAFE",
        "color_icono_social": "#FFFFFF",
        "color_fondo_icono_social": "#1E3A8A",
        "color_fab_fondo": "#25D366",
        "color_fab_icono": "#FFFFFF",
    },
}

# Apariencia editable, en el orden de las columnas.
_APARIENCIA_EXAMPLE = {
    "tipografia": 1,
    "color_fondo": "#FFFFFF",
    "color_superficie": "#F5F7FA",
    "color_borde": "#E2E8F0",
    "color_titulo": "#1A202C",
    "color_texto": "#2D3748",
    "color_texto_secundario": "#718096",
    "color_primario": "#2B6CB0",
    "color_texto_sobre_primario": "#FFFFFF",
    "color_secundario": "#EDF2F7",
    "color_texto_sobre_secundario": "#2D3748",
    "color_overlay_portada": "#000000",
    "overlay_opacidad": 40,
    "color_precio": "#2F855A",
    "color_destacado": "#D69E2E",
    "color_texto_sobre_destacado": "#FFFFFF",
    "color_icono": "#2B6CB0",
    "color_fondo_icono": "#EBF8FF",
    "icono_forma": "circulo",
    "color_icono_social": "#FFFFFF",
    "color_fondo_icono_social": "#2B6CB0",
    "color_fab_fondo": "#25D366",
    "color_fab_icono": "#FFFFFF",
    "fab_posicion": "derecha",
}
TARJETA_THEME_RESPONSE_EXAMPLE = {
    "id": "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b",
    "preset": "claro",
    **_APARIENCIA_EXAMPLE,
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
TARJETA_THEME_CREATE_EXAMPLE = {"preset": "claro", "tipografia": 1}
TARJETA_THEME_PUBLIC_EXAMPLE = _APARIENCIA_EXAMPLE


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaThemeCreate(SchemaBase):
    """
    Extensión 1:1: se crea junto con la tarjeta y con su mismo id. Los colores
    los copia el service del preset elegido.
    """

    preset: PresetTheme = PresetTheme.CLARO
    tipografia: int = Field(default=1, le=SMALLINT_MAX)

    @field_validator("tipografia", mode="before")
    @classmethod
    def validate_tipografia(cls, value: object) -> int:
        return validator_positive_integer(value)

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_THEME_CREATE_EXAMPLE})


class TarjetaThemeUpdate(SchemaBase):
    """
    PATCH /tarjeta-themes/{id}. Cambiar un color a mano deja preset = NULL
    (personalizado); el preset se aplica con POST /{id}/aplicar-preset.
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
    """POST /tarjeta-themes/{id}/aplicar-preset: copia los colores del preset."""

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
