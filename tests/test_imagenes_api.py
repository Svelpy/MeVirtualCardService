"""Subida de imágenes pendientes y su validación al usarlas, con Cloudinary simulado."""

from uuid import uuid4

from tests.conftest import PLAN_PRO_ID, auth_header, uploaded_image_url


UPLOADS = "/api/v1/imagenes/uploads"
PAGOS = "/api/v1/pagos/registrar"


def _pago(usuario, comprobante_url: str) -> dict:
    return {
        "user_id": str(usuario.id),
        "plan_id": str(PLAN_PRO_ID),
        "metodo": "qr",
        "comprobante_url": comprobante_url,
        "idempotency_key": uuid4().hex,
    }


async def test_cualquier_rol_sube_una_imagen_y_recibe_su_url(client, user, cloudinary):
    response = await client.post(
        UPLOADS, files={"file": ("foto.jpg", b"\xff\xd8\xff", "image/jpeg")}, headers=auth_header(user)
    )
    assert response.status_code == 201
    assert response.json() == {"url": cloudinary.uploaded[0]}


async def test_subir_exige_sesion_y_un_archivo(client, user):
    files = {"file": ("foto.jpg", b"\xff\xd8\xff", "image/jpeg")}
    assert (await client.post(UPLOADS, files=files)).status_code == 401
    assert (await client.post(UPLOADS, headers=auth_header(user))).status_code == 422


async def test_un_comprobante_subido_se_guarda_y_se_confirma_en_su_carpeta(client, admin, user, cloudinary):
    url = uploaded_image_url()
    response = await client.post(PAGOS, json=_pago(user, url), headers=auth_header(admin))
    assert response.status_code == 201
    assert response.json()["comprobante_url"] == url
    assert cloudinary.confirmed == {url: f"pagos/{user.id}"}


async def test_una_url_que_no_salio_de_uploads_responde_422(client, admin, user, cloudinary):
    for url in ("https://example.com/comprobante.jpg", uploaded_image_url().replace("/imagenes/", "/otra/")):
        response = await client.post(PAGOS, json=_pago(user, url), headers=auth_header(admin))
        assert response.status_code == 422, url
        assert "comprobante_url" in response.json()["details"]
    assert cloudinary.confirmed == {}


async def test_una_imagen_ya_usada_por_otro_registro_responde_422(client, admin, user):
    url = uploaded_image_url()
    assert (await client.post(PAGOS, json=_pago(user, url), headers=auth_header(admin))).status_code == 201
    response = await client.post(PAGOS, json=_pago(user, url), headers=auth_header(admin))
    assert response.status_code == 422
    assert response.json()["details"] == {"comprobante_url": "La imagen ya pertenece a otro registro."}
