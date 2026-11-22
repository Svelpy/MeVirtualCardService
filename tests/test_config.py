import pytest
from pydantic import ValidationError

from tests.conftest import make_settings


@pytest.mark.parametrize(
    ("environment", "docs_enabled", "expected"),
    [
        ("development", None, True),
        ("production", None, False),
        ("production", "true", True),
        ("development", "false", False),
        ("production", "", False),
    ],
)
def test_docs_enabled_sigue_a_debug_salvo_que_se_defina(environment, docs_enabled, expected):
    overrides = {"ENVIRONMENT": environment}
    if docs_enabled is not None:
        overrides["DOCS_ENABLED"] = docs_enabled
    assert make_settings(**overrides).DOCS_ENABLED is expected


def test_debug_solo_en_development():
    assert make_settings(ENVIRONMENT="development").DEBUG is True
    assert make_settings(ENVIRONMENT="staging").DEBUG is False


def test_secret_key_corta_se_rechaza():
    with pytest.raises(ValidationError, match="SECRET_KEY debe contener al menos 32 bytes"):
        make_settings(SECRET_KEY="corta")


def test_claves_iguales_se_rechazan():
    with pytest.raises(ValidationError, match="deben ser diferentes"):
        make_settings(SECRET_KEY="x" * 32, CSRF_SECRET_KEY="x" * 32)


def test_cors_normaliza_origenes():
    settings = make_settings(ENVIRONMENT="production", PROD_ORIGINS=" https://a.com/ ,https://b.com,")
    assert settings.CORS_ORIGINS_LIST == ["https://a.com", "https://b.com"]


def test_produccion_sin_origenes_falla():
    settings = make_settings(ENVIRONMENT="production", PROD_ORIGINS=None)
    with pytest.raises(ValueError, match="PROD_ORIGINS"):
        _ = settings.CORS_ORIGINS_LIST


def test_cookie_segura_fuera_de_development():
    assert make_settings(ENVIRONMENT="development").REFRESH_TOKEN_COOKIE_SECURE is False
    assert make_settings(ENVIRONMENT="production").REFRESH_TOKEN_COOKIE_SECURE is True
