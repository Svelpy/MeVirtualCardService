"""API de vitrina_item (Hija paginada, primera vuelta) contra la base de desarrollo, en una transacción revertida."""

from uuid import uuid4

from sqlalchemy import select

from app.domains.vitrina_categoria.models import VitrinaCategoria
from app.domains.vitrina_item_imagen.models import VitrinaItemImagen
from tests.conftest import auth_header, create_usuario, uploaded_image_url


BASE = "/api/v1/vitrina-items"


async def _vitrina(client, usuario) -> str:
    """La vitrina se crea con la tarjeta y comparte su id."""
    body = {"slug": f"t-{uuid4().hex[:8]}", "rubro": "Pediatría", "nombres": "Ana"}
    response = await client.post("/api/v1/tarjetas/", json=body, headers=auth_header(usuario))
    assert response.status_code == 201
    return response.json()["id"]


async def _categoria(db_session, vitrina_id: str, nombre: str = "Consultas") -> VitrinaCategoria:
    categoria = VitrinaCategoria(vitrina_id=vitrina_id, nombre=nombre)
    db_session.add(categoria)
    await db_session.commit()
    return categoria


async def _item(client, usuario, vitrina_id: str, **overrides) -> dict:
    body = {"vitrina_id": vitrina_id, "titulo": "Consulta", **overrides}
    response = await client.post(f"{BASE}/", json=body, headers=auth_header(usuario))
    assert response.status_code == 201, response.text
    return response.json()


async def test_el_dueno_crea_y_lista_sus_items_en_su_orden(client, db_session, user):
    vitrina_id = await _vitrina(client, user)
    categoria = await _categoria(db_session, vitrina_id)
    segundo = await _item(client, user, vitrina_id, titulo="Control", orden=2)
    primero = await _item(client, user, vitrina_id, titulo="Consulta", orden=1, categoria_id=str(categoria.id), precio="250")
    assert primero["precio"] == "250.00" and primero["categoria_id"] == str(categoria.id)

    body = (await client.get(f"{BASE}/?vitrina_id={vitrina_id}", headers=auth_header(user))).json()
    assert [item["id"] for item in body["data"]] == [primero["id"], segundo["id"]]
    body = (await client.get(f"{BASE}/?categoria_id={categoria.id}", headers=auth_header(user))).json()
    assert body["total"] == 1


async def test_referencias_ajenas_o_inexistentes_responden_422(client, db_session, user):
    otro = await create_usuario(db_session, "otro@test.example.com")
    vitrina_ajena = await _vitrina(client, otro)
    propia = await _vitrina(client, user)
    categoria_ajena = await _categoria(db_session, vitrina_ajena)

    for body, field in (
        ({"vitrina_id": vitrina_ajena, "titulo": "X"}, "vitrina_id"),  # fuera del alcance
        ({"vitrina_id": str(uuid4()), "titulo": "X"}, "vitrina_id"),
        ({"vitrina_id": propia, "titulo": "X", "categoria_id": str(categoria_ajena.id)}, "categoria_id"),
    ):
        response = await client.post(f"{BASE}/", json=body, headers=auth_header(user))
        assert response.status_code == 422, body
        assert field in response.json()["details"]


async def test_datos_invalidos_responden_422(client, user):
    vitrina_id = await _vitrina(client, user)
    for body in (
        {"vitrina_id": vitrina_id, "titulo": ""},
        {"vitrina_id": vitrina_id, "titulo": "X", "precio": "-1"},
        {"vitrina_id": vitrina_id, "titulo": "X", "precio": "10", "precio_anterior": "5"},
        {"vitrina_id": vitrina_id, "titulo": "X", "orden": -1},
        {"titulo": "X"},
    ):
        assert (await client.post(f"{BASE}/", json=body, headers=auth_header(user))).status_code == 422, body

    item = await _item(client, user, vitrina_id, precio="100")
    for body in ({"vitrina_id": vitrina_id}, {"titulo": None}, {"precio_anterior": "90"}):
        response = await client.patch(f"{BASE}/{item['id']}", json=body, headers=auth_header(user))
        assert response.status_code == 422, body
    # Con el precio guardado (100), un precio anterior mayor sí vale.
    response = await client.patch(f"{BASE}/{item['id']}", json={"precio_anterior": "120"}, headers=auth_header(user))
    assert response.status_code == 200


async def test_un_usuario_no_ve_ni_modifica_items_de_otra_tarjeta(client, db_session, user):
    otro = await create_usuario(db_session, "otro@test.example.com")
    ajeno = await _item(client, otro, await _vitrina(client, otro))
    headers = auth_header(user)
    for method, url, body in (
        ("GET", f"{BASE}/{ajeno['id']}", None),
        ("PATCH", f"{BASE}/{ajeno['id']}", {"titulo": "Mío"}),
        ("DELETE", f"{BASE}/{ajeno['id']}", None),
    ):
        response = await client.request(method, url, json=body, headers=headers)
        assert response.status_code == 404, (method, url)
    assert (await client.get(f"{BASE}/?vitrina_id={ajeno['vitrina_id']}", headers=headers)).json()["total"] == 0
    # Auditar no está en su matriz: 403 antes de mirar el alcance.
    assert (await client.get(f"{BASE}/{ajeno['id']}/audit", headers=headers)).status_code == 403


async def test_los_admins_gestionan_items_de_cualquier_tarjeta(client, admin, user):
    vitrina_id = await _vitrina(client, user)
    item = await _item(client, admin, vitrina_id)  # agregar un item es editar la vitrina ajena
    response = await client.patch(f"{BASE}/{item['id']}", json={"destacado": True}, headers=auth_header(admin))
    assert response.status_code == 200 and response.json()["destacado"] is True
    audit = (await client.get(f"{BASE}/{item['id']}/audit", headers=auth_header(admin))).json()
    assert audit["created_by"] == str(admin.id)


async def test_eliminar_cae_sobre_sus_imagenes_y_queda_en_la_auditoria(client, db_session, admin, user):
    item = await _item(client, user, await _vitrina(client, user))
    imagen = VitrinaItemImagen(item_id=item["id"], url=uploaded_image_url(), orden=0)
    db_session.add(imagen)
    await db_session.commit()

    assert (await client.delete(f"{BASE}/{item['id']}", headers=auth_header(user))).status_code == 204
    assert (await client.get(f"{BASE}/{item['id']}", headers=auth_header(user))).status_code == 404
    audit = (await client.get(f"{BASE}/{item['id']}/audit", headers=auth_header(admin))).json()
    assert audit["is_deleted"] is True
    deleted = await db_session.execute(
        select(VitrinaItemImagen.is_deleted).where(VitrinaItemImagen.id == imagen.id).execution_options(populate_existing=True)
    )
    assert deleted.scalar_one() is True


async def test_item_inexistente_responde_404(client, admin):
    for method, url in (("GET", f"{BASE}/{uuid4()}"), ("PATCH", f"{BASE}/{uuid4()}"), ("DELETE", f"{BASE}/{uuid4()}")):
        response = await client.request(method, url, json={} if method == "PATCH" else None, headers=auth_header(admin))
        assert response.status_code == 404, (method, url)


async def test_eliminar_la_tarjeta_elimina_sus_items(client, user):
    vitrina_id = await _vitrina(client, user)
    item = await _item(client, user, vitrina_id)
    await client.delete(f"/api/v1/tarjetas/{vitrina_id}", headers=auth_header(user))
    assert (await client.get(f"{BASE}/{item['id']}", headers=auth_header(user))).status_code == 404
