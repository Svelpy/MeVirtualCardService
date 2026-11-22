"""API de plan (Filas fijas) contra la base de desarrollo, dentro de una transacción revertida."""

from uuid import uuid4

from tests.conftest import PLAN_PRO_ID, auth_header


BASE = "/api/v1/planes"


async def test_la_pagina_de_precios_es_publica_y_solo_muestra_los_visibles(client, admin):
    response = await client.get(f"{BASE}/public")
    assert response.status_code == 200
    assert [plan["codigo"] for plan in response.json()] == ["free", "pro", "business"]
    assert "created_by" not in response.json()[0]

    await client.patch(f"{BASE}/{PLAN_PRO_ID}", json={"is_visible": False}, headers=auth_header(admin))
    response = await client.get(f"{BASE}/public")
    assert [plan["codigo"] for plan in response.json()] == ["free", "business"]


async def test_el_admin_lista_lee_y_audita(client, admin):
    response = await client.get(f"{BASE}/", headers=auth_header(admin))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3 and body["total_pages"] == 1 and len(body["data"]) == 3

    response = await client.get(f"{BASE}/?is_visible=false", headers=auth_header(admin))
    assert response.json()["total"] == 0

    response = await client.get(f"{BASE}/{PLAN_PRO_ID}", headers=auth_header(admin))
    assert response.status_code == 200
    assert response.json()["codigo"] == "pro"

    response = await client.get(f"{BASE}/{PLAN_PRO_ID}/audit", headers=auth_header(admin))
    assert response.status_code == 200
    assert response.json()["is_deleted"] is False


async def test_el_admin_edita_todo_menos_el_codigo(client, admin):
    response = await client.patch(
        f"{BASE}/{PLAN_PRO_ID}",
        json={"nombre": "Profesional", "precio": "90.5", "moneda": "bob"},
        headers=auth_header(admin),
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["nombre"], body["precio"], body["moneda"]) == ("Profesional", "90.50", "BOB")
    assert body["duracion_dias"] == 365  # lo que no se envía no cambia

    audit = (await client.get(f"{BASE}/{PLAN_PRO_ID}/audit", headers=auth_header(admin))).json()
    assert audit["updated_by"] == str(admin.id)


async def test_el_user_no_tiene_acceso(client, user):
    # 403: la matriz no le da ninguna acción sobre PLAN.
    for method, url in (("GET", f"{BASE}/"), ("GET", f"{BASE}/{PLAN_PRO_ID}"), ("GET", f"{BASE}/{PLAN_PRO_ID}/audit")):
        response = await client.request(method, url, headers=auth_header(user))
        assert response.status_code == 403, url
    response = await client.patch(f"{BASE}/{PLAN_PRO_ID}", json={"nombre": "Gratis"}, headers=auth_header(user))
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_sin_token_responde_401(client):
    assert (await client.get(f"{BASE}/")).status_code == 401


async def test_plan_inexistente_responde_404(client, admin):
    response = await client.get(f"{BASE}/{uuid4()}", headers=auth_header(admin))
    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"
    response = await client.patch(f"{BASE}/{uuid4()}", json={"nombre": "X"}, headers=auth_header(admin))
    assert response.status_code == 404


async def test_datos_invalidos_responden_422(client, admin):
    for body in (
        {"codigo": "gold"},  # el código no se edita
        {"nombre": None},  # columna no nullable
        {"precio": "-1"},
        {"duracion_dias": 0},
        {"moneda": "DOLAR"},
    ):
        response = await client.patch(f"{BASE}/{PLAN_PRO_ID}", json=body, headers=auth_header(admin))
        assert response.status_code == 422, body
        assert response.json()["code"] == "VALIDATION_ERROR"
