from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest

from app.shared.services.validators import (
    validator_boolean,
    validator_date,
    validator_datetime,
    validator_email,
    validator_hex_color,
    validator_http_url,
    validator_integer,
    validator_json_object,
    validator_latitude,
    validator_longitude,
    validator_name,
    validator_non_empty_text,
    validator_non_negative_integer,
    validator_non_negative_money,
    validator_password,
    validator_percentage,
    validator_phone,
    validator_positive_integer,
    validator_positive_money,
    validator_slug,
    validator_slug_source,
    validator_text,
    validator_time,
)


@pytest.mark.parametrize(
    ("validator", "value", "expected"),
    [
        (validator_name, "  José-María O'Neil ", "José-María O'Neil"),
        (validator_phone, " +59170000001 ", "+59170000001"),
        (validator_password, "Clave123", "Clave123"),
        (validator_password, "una frase larga de 64 caracteres o menos sirve", "una frase larga de 64 caracteres o menos sirve"),
        (validator_email, "  Ana@Example.COM ", "ana@example.com"),
        (validator_text, "  ", ""),
        (validator_non_empty_text, "  hola ", "hola"),
        (validator_http_url, " https://example.com/a ", "https://example.com/a"),
        (validator_slug_source, " Mi Producto ", "Mi Producto"),
        (validator_boolean, False, False),
        (validator_integer, -3, -3),
        (validator_non_negative_integer, 0, 0),
        (validator_non_negative_money, "10.50", Decimal("10.50")),
        (validator_positive_money, 1, Decimal("1")),
        (validator_date, "2026-01-31", date(2026, 1, 31)),
        (validator_datetime, "2026-01-31T14:30:00+00:00", datetime(2026, 1, 31, 14, 30, tzinfo=timezone.utc)),
        (validator_slug, " mi-producto-2 ", "mi-producto-2"),
        (validator_positive_integer, 3, 3),
        (validator_percentage, "12.5", Decimal("12.5")),
        (validator_time, "09:30", time(9, 30)),
        (validator_latitude, "-16.5", Decimal("-16.5")),
        (validator_longitude, -68.15, Decimal("-68.15")),
        (validator_hex_color, "ff00aa", "#FF00AA"),
        (validator_json_object, '{"a": 1}', {"a": 1}),
    ],
)
def test_valor_valido_se_normaliza(validator, value, expected):
    assert validator(value) == expected


@pytest.mark.parametrize(
    ("validator", "value"),
    [
        (validator_name, "Ana3"),
        (validator_phone, "12-34"),
        (validator_password, "1234567"),
        (validator_password, "x" * 65),
        (validator_email, 123),
        (validator_non_empty_text, "   "),
        (validator_http_url, "ftp://example.com"),
        (validator_slug_source, "!!!"),
        (validator_boolean, "true"),
        (validator_integer, True),
        (validator_integer, "5"),
        (validator_non_negative_integer, -1),
        (validator_non_negative_money, "abc"),
        (validator_non_negative_money, -1),
        (validator_positive_money, 0),
        (validator_date, "31/01/2026"),
        (validator_date, datetime(2026, 1, 31, 10, 0)),
        (validator_datetime, "2026-01-31T14:30:00"),
        (validator_datetime, "no-es-fecha"),
        (validator_slug, "Mi Producto"),
        (validator_slug, "-inicio"),
        (validator_positive_integer, 0),
        (validator_percentage, 101),
        (validator_time, "24:00"),
        (validator_time, "9:30"),
        (validator_latitude, 91),
        (validator_longitude, "-181"),
        (validator_hex_color, "#GG0000"),
        (validator_json_object, "[1, 2]"),
        (validator_json_object, "{no json}"),
    ],
)
def test_valor_invalido_lanza_value_error(validator, value):
    with pytest.raises(ValueError):
        validator(value)


@pytest.mark.parametrize(
    "validator",
    [validator_name, validator_phone, validator_password, validator_email, validator_text, validator_date],
)
def test_none_no_se_acepta(validator):
    with pytest.raises(ValueError):
        validator(None)
