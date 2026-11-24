"""presets de theme del frontend

Revision ID: a3f9c2d71b04
Revises: ec8dbbb53c1c
Create Date: 2026-11-24 10:00:00.000000

Los presets pasan a ser los 10 que define el frontend (TEMAS_TARJETA), y cada uno
define, además de los colores, overlay_opacidad, icono_forma y fab_posicion.

- Agrega al tipo preset_theme: calido, natural, belleza, creativo, energia.
- Los themes que siguen con uno de los 5 presets anteriores (preset no NULL, es
  decir, no personalizados) toman los valores nuevos de su preset, para que el
  nombre del preset y sus valores sigan coincidiendo. Los personalizados no se tocan.

Los valores están copiados aquí, no importados de app/: una migración no cambia
aunque después cambien los presets del código.

En downgrade los themes con un preset nuevo quedan personalizados (preset NULL,
conservan sus valores) y el tipo vuelve a los 5 presets. Los valores que se
actualizaron en upgrade no se restauran.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a3f9c2d71b04'
down_revision: Union[str, Sequence[str], None] = 'ec8dbbb53c1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_PRESETS = ['claro', 'oscuro', 'elegante', 'salud', 'corporativo']
NEW_PRESETS = ['calido', 'natural', 'belleza', 'creativo', 'energia']

# Valores nuevos de los 5 presets que ya existían.
PRESET_VALUES = {
    "claro": {
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
        "icono_forma": "circulo",
        "color_icono_social": "#374151",
        "color_fondo_icono_social": "#F3F4F6",
        "color_fab_fondo": "#2563EB",
        "color_fab_icono": "#FFFFFF",
        "fab_posicion": "derecha"
    },
    "oscuro": {
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
        "icono_forma": "redondeado",
        "color_icono_social": "#E5E7EB",
        "color_fondo_icono_social": "#273041",
        "color_fab_fondo": "#60A5FA",
        "color_fab_icono": "#0B1220",
        "fab_posicion": "derecha"
    },
    "elegante": {
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
        "icono_forma": "cuadrado",
        "color_icono_social": "#1C1917",
        "color_fondo_icono_social": "#F1EADF",
        "color_fab_fondo": "#1C1917",
        "color_fab_icono": "#F5E6C8",
        "fab_posicion": "derecha"
    },
    "salud": {
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
        "icono_forma": "circulo",
        "color_icono_social": "#0F766E",
        "color_fondo_icono_social": "#E6F6F3",
        "color_fab_fondo": "#0F766E",
        "color_fab_icono": "#FFFFFF",
        "fab_posicion": "derecha"
    },
    "corporativo": {
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
        "icono_forma": "redondeado",
        "color_icono_social": "#1E293B",
        "color_fondo_icono_social": "#F1F5F9",
        "color_fab_fondo": "#1E3A8A",
        "color_fab_icono": "#FFFFFF",
        "fab_posicion": "derecha"
    }
}


def upgrade() -> None:
    """Upgrade schema."""
    # ADD VALUE puede ir en la transacción: los valores nuevos no se usan en ella.
    for preset in NEW_PRESETS:
        op.execute(f"ALTER TYPE preset_theme ADD VALUE IF NOT EXISTS '{preset}'")

    # Los valores son fijos y conocidos: van como literales, así la migración también
    # se puede revisar en modo offline (alembic upgrade --sql).
    for preset, values in PRESET_VALUES.items():
        assignments = ", ".join(f"{field} = {_literal(field, value)}" for field, value in values.items())
        op.execute(f"UPDATE tarjeta_theme SET {assignments} WHERE preset = '{preset}'")


def downgrade() -> None:
    """Downgrade schema."""
    names = ", ".join(f"'{preset}'" for preset in NEW_PRESETS)
    op.execute(f"UPDATE tarjeta_theme SET preset = NULL WHERE preset::text IN ({names})")
    op.execute("ALTER TYPE preset_theme RENAME TO preset_theme_old")
    values = ", ".join(f"'{preset}'" for preset in OLD_PRESETS)
    op.execute(f"CREATE TYPE preset_theme AS ENUM ({values})")
    op.execute(
        "ALTER TABLE tarjeta_theme ALTER COLUMN preset TYPE preset_theme USING preset::text::preset_theme"
    )
    op.execute("DROP TYPE preset_theme_old")


def _literal(field: str, value: object) -> str:
    """Literal SQL de un valor del preset; los enums de la tabla van con su tipo."""
    enum_types = {"icono_forma": "forma_icono", "fab_posicion": "posicion_fab"}
    if isinstance(value, int):
        return str(value)
    if field in enum_types:
        return f"'{value}'::{enum_types[field]}"
    return f"'{value}'"
