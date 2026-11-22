from app.core.config import Settings


def make_settings(**overrides: object) -> Settings:
    """Settings de prueba que no leen el .env."""
    values: dict[str, object] = {
        "_env_file": None,
        "SECRET_KEY": "s" * 32,
        "CSRF_SECRET_KEY": "c" * 32,
        "PROD_ORIGINS": "https://app.example.com",
    }
    values.update(overrides)
    return Settings(**values)
