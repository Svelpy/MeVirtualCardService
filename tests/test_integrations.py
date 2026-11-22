import cloudinary
import pytest
import resend

from app.integrations.cloudinary import CloudinaryService, configure_cloudinary
from app.integrations.resend import ResendService, configure_resend
from tests.conftest import make_settings

CLOUDINARY_URL = "https://res.cloudinary.com/demo/image/upload/v1/carpeta/imagen.png"


@pytest.fixture(autouse=True)
def sin_configuracion(monkeypatch):
    """Cada test empieza con los dos SDK sin configurar."""
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    cloudinary.reset_config()
    monkeypatch.setattr(resend, "api_key", None)


def test_sin_credenciales_la_app_arranca():
    settings = make_settings()
    configure_cloudinary(settings)
    configure_resend(settings)


async def test_cloudinary_sin_credenciales_falla_al_usarse():
    configure_cloudinary(make_settings())
    with pytest.raises(RuntimeError, match="Cloudinary no está configurado"):
        await CloudinaryService.delete_image(CLOUDINARY_URL)


async def test_cloudinary_ignora_urls_ajenas_aunque_no_este_configurado():
    assert await CloudinaryService.delete_image("https://otro.com/imagen.png") is False


async def test_resend_sin_api_key_falla_al_usarse():
    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        await ResendService.send_email(make_settings(), to="a@example.com", subject="s", html="h")


async def test_resend_no_envia_reply_to_vacio(monkeypatch):
    enviado: dict[str, object] = {}

    async def fake_send(params, options):
        enviado.update(params)
        return {"id": "email_1"}

    monkeypatch.setattr(resend.Emails, "send_async", fake_send)
    settings = make_settings(RESEND_API_KEY="re_test", RESEND_FROM_EMAIL="Proyecto <no-reply@example.com>")
    configure_resend(settings)

    assert await ResendService.send_email(settings, to="a@example.com", subject="s", html="h") == "email_1"
    assert "reply_to" not in enviado
