"""
API de vitrina_item (Hija embebida de la vitrina): se escribe con PATCH /vitrinas/{id}
y solo expone su auditoría. Contra la base de desarrollo, en una transacción revertida.
"""

from uuid import uuid4

from app.domains.vitrina_item.schemas import VITRINA_ITEM_MAX
from app.domains.vitrina_item_imagen.schemas import VITRINA_ITEM_IMAGEN_MAX
from tests.conftest import auth_header, create_usuario, uploaded_image_url


VITRINAS = "/api/v1/vitrinas"
ITEMS = "/api/v1/vitrina-items"


async def _vitrina(client, usuario, **vitrina) -> str:
    """La vitrina se crea con la tarjeta y comparte su id."""
    body = {"slug": f"t-{uuid4().hex[:8]}", "rubro": "Pediatría", "nombres": "Ana"}
    if vitrina:
        body["vitrina"] = vitrina
    response = await client.post("/api/v1/tarjetas/", json=body, headers=auth_header(usuario))
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _patch(client, usuario, vitrina_id: str, body: dict):
    return await client.patch(f"{VITRINAS}/{vitrina_id}", json=body, headers=auth_header(usuario))


async def _ok(client, usuario, vitrina_id: str, body: dict) -> dict:
    response = await _patch(client, usuario, vitrina_id, body)
    assert response.status_code == 200, response.text
    return response.json()


async def test_los_items_se_escriben_desde_la_vitrina_en_su_orden(client, user):
    vitrina_id = await _vitrina(client, user, categorias=[{"nombre": "Consultas"}])
    vitrina = (await client.get(f"{VITRINAS}/{vitrina_id}", headers=auth_header(user))).json()
    categoria = vitrina["categorias"][0]
    assert vitrina["items"] == []

    body = await _ok(
        client,
        user,
        vitrina_id,
        {
            "items": [
                {"titulo": "Control", "orden": 2},
                {"titulo": "Consulta", "orden": 1, "categoria_id": categoria["id"], "precio": "250"},
            ]
        },
    )
    primero, segundo = body["items"]
    assert (primero["titulo"], segundo["titulo"]) == ("Consulta", "Control")
    assert primero["precio"] == "250.00" and primero["vitrina_id"] == vitrina_id
    assert primero["categoria"]["nombre"] == "Consultas" and segundo["categoria"] is None

    # Con id se actualiza; el que no viene se elimina; sin id se crea.
    body = await _ok(
        client,
        user,
        vitrina_id,
        {"items": [{"id": primero["id"], "titulo": "Consulta general", "orden": 0}, {"titulo": "Taller", "orden": 1}]},
    )
    assert [(i["id"] == primero["id"], i["titulo"]) for i in body["items"]] == [(True, "Consulta general"), (False, "Taller")]
    assert body["items"][0]["categoria_id"] is None  # la lista es el estado final de cada item

    # Ausente no toca los items; [] los elimina.
    assert len((await _ok(client, user, vitrina_id, {"mostrar_precios": False}))["items"]) == 2
    assert (await _ok(client, user, vitrina_id, {"items": []}))["items"] == []


async def test_la_vitrina_se_crea_con_sus_items_sin_categoria(client, user, cloudinary):
    imagen = uploaded_image_url()
    vitrina_id = await _vitrina(
        client, user, items=[{"titulo": "Consulta", "imagenes": [{"url": imagen, "orden": 0}]}]
    )
    vitrina = (await client.get(f"{VITRINAS}/{vitrina_id}", headers=auth_header(user))).json()
    assert [i["titulo"] for i in vitrina["items"]] == ["Consulta"]
    assert vitrina["items"][0]["imagenes"][0]["url"] == imagen
    assert cloudinary.confirmed[imagen] == f"tarjetas/{vitrina_id}/vitrina"

    # Las categorías nuevas no tienen id todavía: un item no puede apuntarlas al crear.
    body = {
        "slug": f"t-{uuid4().hex[:8]}",
        "rubro": "Pediatría",
        "nombres": "Ana",
        "vitrina": {"items": [{"titulo": "X", "categoria_id": str(uuid4())}]},
    }
    response = await client.post("/api/v1/tarjetas/", json=body, headers=auth_header(user))
    assert response.status_code == 422


async def test_los_topes_de_items_y_de_imagenes(client, user):
    vitrina_id = await _vitrina(client, user)
    items = [{"titulo": f"Item {n}", "orden": n} for n in range(VITRINA_ITEM_MAX)]
    assert len((await _ok(client, user, vitrina_id, {"items": items}))["items"]) == VITRINA_ITEM_MAX
    response = await _patch(client, user, vitrina_id, {"items": [*items, {"titulo": "Uno más"}]})
    assert response.status_code == 422

    imagenes = [{"url": uploaded_image_url(), "orden": n} for n in range(VITRINA_ITEM_IMAGEN_MAX + 1)]
    response = await _patch(client, user, vitrina_id, {"items": [{"titulo": "X", "imagenes": imagenes}]})
    assert response.status_code == 422


async def test_referencias_ajenas_o_inexistentes_responden_422(client, db_session, user):
    otro = await create_usuario(db_session, "otro@test.example.com")
    ajena = await _vitrina(client, otro, categorias=[{"nombre": "Ajena"}])
    categoria_ajena = (await client.get(f"{VITRINAS}/{ajena}", headers=auth_header(otro))).json()["categorias"][0]
    item_ajeno = (await _ok(client, otro, ajena, {"items": [{"titulo": "Ajeno"}]}))["items"][0]

    propia = await _vitrina(client, user, categorias=[{"nombre": "Consultas"}])
    categoria = (await client.get(f"{VITRINAS}/{propia}", headers=auth_header(user))).json()["categorias"][0]

    for body, field in (
        ({"items": [{"titulo": "X", "categoria_id": categoria_ajena["id"]}]}, "items -> 0 -> categoria_id"),
        ({"items": [{"titulo": "X", "categoria_id": str(uuid4())}]}, "items -> 0 -> categoria_id"),
        # La categoría se elimina en la misma petición.
        ({"categorias": [], "items": [{"titulo": "X", "categoria_id": categoria["id"]}]}, "items -> 0 -> categoria_id"),
        ({"items": [{"id": item_ajeno["id"], "titulo": "Mío"}]}, "items"),  # un item de otra vitrina
    ):
        response = await _patch(client, user, propia, body)
        assert response.status_code == 422, body
        assert field in response.json()["details"], response.json()


async def test_datos_invalidos_responden_422(client, user):
    vitrina_id = await _vitrina(client, user)
    for item in (
        {"titulo": ""},
        {"titulo": "X", "precio": "-1"},
        {"titulo": "X", "precio": "10", "precio_anterior": "5"},
        {"titulo": "X", "precio_anterior": "5"},
        {"titulo": "X", "orden": -1},
        {"titulo": "X", "vitrina_id": vitrina_id},  # la asigna el service
        {"precio": "10"},
    ):
        assert (await _patch(client, user, vitrina_id, {"items": [item]})).status_code == 422, item


async def test_una_categoria_se_elimina_en_la_misma_peticion_que_deja_de_usarse(client, user):
    vitrina_id = await _vitrina(client, user, categorias=[{"nombre": "Consultas"}, {"nombre": "Talleres"}])
    consultas, talleres = (await client.get(f"{VITRINAS}/{vitrina_id}", headers=auth_header(user))).json()["categorias"]
    item = (await _ok(client, user, vitrina_id, {"items": [{"titulo": "X", "categoria_id": consultas["id"]}]}))["items"][0]

    # Sin tocar los items, la categoría en uso no se elimina.
    response = await _patch(client, user, vitrina_id, {"categorias": [{"id": talleres["id"], "nombre": "Talleres"}]})
    assert response.status_code == 409

    body = await _ok(
        client,
        user,
        vitrina_id,
        {
            "categorias": [{"id": talleres["id"], "nombre": "Talleres"}],
            "items": [{"id": item["id"], "titulo": "X", "categoria_id": talleres["id"]}],
        },
    )
    assert [c["nombre"] for c in body["categorias"]] == ["Talleres"]
    assert body["items"][0]["categoria"]["nombre"] == "Talleres"


async def test_eliminar_un_item_cae_sobre_sus_imagenes_y_queda_en_la_auditoria(client, admin, user, cloudinary):
    vitrina_id = await _vitrina(client, user)
    imagen = uploaded_image_url()
    item = (await _ok(client, user, vitrina_id, {"items": [{"titulo": "X", "imagenes": [{"url": imagen}]}]}))["items"][0]
    imagen_id = item["imagenes"][0]["id"]

    await _ok(client, user, vitrina_id, {"items": []})
    audit = (await client.get(f"{ITEMS}/{item['id']}/audit", headers=auth_header(admin))).json()
    assert audit["is_deleted"] is True and audit["deleted_by"] == str(user.id)
    audit = (await client.get(f"/api/v1/vitrina-item-imagenes/{imagen_id}/audit", headers=auth_header(admin))).json()
    assert audit["is_deleted"] is True
    assert cloudinary.deleted == []  # la imagen queda para la auditoría


async def test_solo_se_expone_la_auditoria(client, admin, user):
    vitrina_id = await _vitrina(client, user)
    item = (await _ok(client, admin, vitrina_id, {"items": [{"titulo": "X"}]}))["items"][0]  # el admin edita la ajena
    audit = (await client.get(f"{ITEMS}/{item['id']}/audit", headers=auth_header(admin))).json()
    assert audit["created_by"] == str(admin.id)
    assert (await client.get(f"{ITEMS}/{item['id']}/audit", headers=auth_header(user))).status_code == 403
    assert (await client.get(f"{ITEMS}/{uuid4()}/audit", headers=auth_header(admin))).status_code == 404

    for method, url in (("GET", f"{ITEMS}/"), ("POST", f"{ITEMS}/"), ("GET", f"{ITEMS}/{item['id']}"), ("DELETE", f"{ITEMS}/{item['id']}")):
        response = await client.request(method, url, headers=auth_header(admin))
        assert response.status_code in (404, 405), (method, url)


async def test_eliminar_la_tarjeta_elimina_sus_items(client, admin, user):
    vitrina_id = await _vitrina(client, user)
    item = (await _ok(client, user, vitrina_id, {"items": [{"titulo": "X"}]}))["items"][0]
    await client.delete(f"/api/v1/tarjetas/{vitrina_id}", headers=auth_header(user))
    audit = (await client.get(f"{ITEMS}/{item['id']}/audit", headers=auth_header(admin))).json()
    assert audit["is_deleted"] is True
