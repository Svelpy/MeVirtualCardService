"""
Librería de validadores reutilizables, sin acceso a base de datos (AGENTS.md §21).

Todos siguen la firma object → T: reciben el valor tal como llegó, comprueban su
tipo antes de usarlo, devuelven el valor validado o normalizado y lanzan
ValueError con un mensaje en español para el cliente. Nunca devuelven None: qué
hacer con un None lo decide el field_validator del schema.

Un validador nuevo se agrega aquí solo si sirve a más de un dominio.
"""

import json
import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from app.shared.services.slug import generate_slug


# =================================
# Texto
# =================================

def validator_text(value: object) -> str:
    """Normaliza texto libre, incluido el texto vacío."""
    if not isinstance(value, str):
        raise ValueError("El valor debe ser texto.")
    return value.strip()


def validator_non_empty_text(value: object) -> str:
    """Normaliza texto libre y rechaza valores vacíos."""
    normalized_text = validator_text(value)
    if not normalized_text:
        raise ValueError("El texto no puede estar vacío.")
    return normalized_text


def validator_name(value: object) -> str:
    """Nombre de persona: letras, espacios, guiones y apóstrofes."""
    if not isinstance(value, str):
        raise ValueError("El nombre debe ser texto.")
    normalized_name = value.strip()
    if not re.fullmatch(r"^[a-zA-ZáéíóúÁÉÍÓÚüÜñÑ\s'-]+$", normalized_name):
        raise ValueError(
            "El nombre solo permite letras, espacios, guiones y apóstrofes."
        )
    return normalized_name


def validator_slug_source(value: object) -> str:
    """Valida texto no vacío capaz de producir un slug."""
    normalized_text = validator_non_empty_text(value)
    if not generate_slug(normalized_text):
        raise ValueError("El texto debe contener al menos una letra o un número válido.")
    return normalized_text


def validator_slug(value: object) -> str:
    """Valida un slug ya formado: minúsculas, dígitos y guiones simples."""
    if not isinstance(value, str):
        raise ValueError("El slug debe ser texto.")
    normalized_slug = value.strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized_slug):
        raise ValueError("El slug solo permite minúsculas, dígitos y guiones, sin guiones al inicio o al final.")
    return normalized_slug


# =================================
# Contacto
# =================================

def validator_email(value: object) -> str:
    """Normaliza un email; su formato lo valida EmailStr en el schema."""
    if not isinstance(value, str):
        raise ValueError("El email debe ser texto.")
    return value.strip().lower()


def validator_phone(value: object) -> str:
    """Teléfono de 6 a 20 dígitos, o con prefijo internacional +."""
    if not isinstance(value, str):
        raise ValueError("El número de teléfono debe ser texto.")
    normalized_phone = value.strip()
    if not re.fullmatch(r"(?:\d{6,20}|\+\d{6,19})", normalized_phone):
        raise ValueError(
            "El teléfono debe contener entre 6 y 20 dígitos, o comenzar con + seguido de entre 6 y 19 dígitos."
        )
    return normalized_phone


def validator_http_url(value: object) -> str:
    """Normaliza una URL HTTP(S) absoluta."""
    if not isinstance(value, str):
        raise ValueError("La URL debe ser texto.")
    normalized_url = value.strip()
    parsed_url = urlparse(normalized_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("La URL debe ser una dirección HTTP o HTTPS válida.")
    return normalized_url


# =================================
# Seguridad
# =================================

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 64


def validator_password(value: object) -> str:
    """
    Contraseña de 8 a 64 caracteres, según OWASP (Authentication Cheat Sheet):
    menos de 8 se considera débil, y un máximo bajo impide usar frases o
    contraseñas de un gestor. No se exigen reglas de composición ni se recortan
    espacios: forman parte de la contraseña.
    """
    if not isinstance(value, str):
        raise ValueError("La contraseña debe ser texto.")
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres.")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"La contraseña no debe superar {PASSWORD_MAX_LENGTH} caracteres.")
    return value


# =================================
# Números
# =================================

def validator_integer(value: object) -> int:
    """Valida un entero, positivo o negativo, sin aceptar booleanos ni textos."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("El valor debe ser un número entero.")
    return value


def validator_non_negative_integer(value: object) -> int:
    """Valida un entero mayor o igual a cero sin aceptar booleanos."""
    value = validator_integer(value)
    if value < 0:
        raise ValueError("El valor debe ser mayor o igual a cero.")
    return value


def validator_positive_integer(value: object) -> int:
    """Valida un entero mayor que cero, como una cantidad."""
    value = validator_integer(value)
    if value <= 0:
        raise ValueError("El valor debe ser mayor que cero.")
    return value


def _to_decimal(value: object, label: str) -> Decimal:
    """Convierte un número o su texto a Decimal finito, sin aceptar booleanos."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, float, str)):
        raise ValueError(f"{label} debe ser un número válido.")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{label} no puede estar vacío.")
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise ValueError(f"{label} debe ser un número válido.") from error
    if not number.is_finite():
        raise ValueError(f"{label} debe ser finito.")
    return number


def validator_non_negative_money(value: object) -> Decimal:
    """Convierte un importe finito y mayor o igual a cero a Decimal."""
    amount = _to_decimal(value, "El importe")
    if amount < 0:
        raise ValueError("El importe debe ser mayor o igual a cero.")
    return amount


def validator_positive_money(value: object) -> Decimal:
    """Convierte un importe finito y positivo a Decimal."""
    amount = validator_non_negative_money(value)
    if amount == 0:
        raise ValueError("El importe debe ser mayor que cero.")
    return amount


def validator_percentage(value: object) -> Decimal:
    """Porcentaje entre 0 y 100, como Decimal."""
    percentage = _to_decimal(value, "El porcentaje")
    if not Decimal(0) <= percentage <= Decimal(100):
        raise ValueError("El porcentaje debe estar entre 0 y 100.")
    return percentage


# =================================
# Fechas y horas
# =================================

def validator_date(value: object) -> date:
    """Valida una fecha sin hora, como objeto date o texto ISO AAAA-MM-DD."""
    if isinstance(value, datetime):
        raise ValueError("La fecha no debe incluir hora.")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("La fecha debe tener el formato AAAA-MM-DD.")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as error:
        raise ValueError("La fecha debe tener el formato AAAA-MM-DD.") from error


def validator_datetime(value: object) -> datetime:
    """Valida fecha y hora ISO 8601 con zona horaria, como objeto datetime o texto."""
    message = "La fecha y hora debe tener el formato ISO 8601, por ejemplo 2026-01-31T14:30:00-04:00."
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip())
        except ValueError as error:
            raise ValueError(message) from error
    if not isinstance(value, datetime):
        raise ValueError(message)
    if value.tzinfo is None:
        raise ValueError("La fecha y hora debe incluir la zona horaria.")
    return value


def validator_time(value: object) -> time:
    """Valida una hora del día HH:MM, como objeto time o texto."""
    if isinstance(value, time):
        return value
    if not isinstance(value, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value.strip()):
        raise ValueError("La hora debe tener el formato HH:MM.")
    return time.fromisoformat(value.strip())


# =================================
# Ubicación
# =================================

def validator_latitude(value: object) -> Decimal:
    """Latitud entre -90 y 90."""
    latitude = _to_decimal(value, "La latitud")
    if not Decimal(-90) <= latitude <= Decimal(90):
        raise ValueError("La latitud debe estar entre -90 y 90.")
    return latitude


def validator_longitude(value: object) -> Decimal:
    """Longitud entre -180 y 180."""
    longitude = _to_decimal(value, "La longitud")
    if not Decimal(-180) <= longitude <= Decimal(180):
        raise ValueError("La longitud debe estar entre -180 y 180.")
    return longitude


# =================================
# Otros
# =================================

def validator_boolean(value: object) -> bool:
    """Valida un booleano real, sin convertir textos ni números."""
    if not isinstance(value, bool):
        raise ValueError("El valor debe ser verdadero o falso.")
    return value


def validator_hex_color(value: object) -> str:
    """Normaliza un color hexadecimal al formato #RRGGBB en mayúsculas."""
    if not isinstance(value, str):
        raise ValueError("El código de color debe ser texto.")
    normalized_color = value.strip().upper()
    if not normalized_color.startswith("#"):
        normalized_color = f"#{normalized_color}"
    if not re.fullmatch(r"#[0-9A-F]{6}", normalized_color):
        raise ValueError("El código de color debe tener el formato #RRGGBB.")
    return normalized_color


def validator_json_object(value: object) -> dict[str, object]:
    """
    Acepta un objeto o su texto JSON, como llega en multipart/form-data, y
    devuelve el objeto.
    """
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        raise ValueError("El valor debe ser un objeto JSON.")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("El valor debe ser un objeto JSON válido.") from error
    if not isinstance(parsed, dict):
        raise ValueError("El valor debe ser un objeto JSON.")
    return parsed
