"""API de pago (Registro / kardex) contra la base de desarrollo, dentro de una transacción revertida."""

from datetime import datetime, timedelta
from uuid import uuid4

from app.core.base_model import utc_now
from tests.conftest import PLAN_FREE_ID, PLAN_PRO_ID, auth_header, create_usuario


BASE = "/api/v1/pagos"
PLAN_BUSINESS_ID = "7b1e9c40-0000-4000-8000-000000000003"


def _pago(usuario, **overrides) -> dict:
    return {"user_id": str(usuario.id), "plan_id": str(PLAN_PRO_ID), "metodo": "qr", "idempotency_key": uuid4().hex, **overrides}


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def _me(client, usuario) -> dict:
    return (await client.get("/api/v1/usuarios/me", headers=auth_header(usuario))).json()


# ---------- Registrar ----------

async def test_sin_monto_cobra_el_precio_y_extiende_desde_el_vencimiento_vigente(client, admin, user):
    vence_free = user.plan_vence_at
    response = await client.post(f"{BASE}/registrar", json=_pago(user), headers=auth_header(admin))
    assert response.status_code == 201
    body = response.json()
    assert (body["monto"], body["moneda"], body["reverses_id"]) == ("80.00", "USD", None)
    assert _dt(body["periodo_inicio"]) == vence_free  # el free seguía vigente: empieza al vencer
    assert _dt(body["periodo_fin"]) == vence_free + timedelta(days=365)
    assert body["user"]["id"] == str(user.id) and body["plan"]["codigo"] == "pro"

    me = await _me(client, user)
    assert me["plan_id"] == str(PLAN_PRO_ID)
    assert _dt(me["plan_vence_at"]) == _dt(body["periodo_fin"])

    audit = (await client.get(f"{BASE}/{body['id']}/audit", headers=auth_header(admin))).json()
    assert audit["created_by"] == str(admin.id)


async def test_con_plan_vencido_el_periodo_empieza_ahora(client, db_session, admin):
    vencido = await create_usuario(db_session, "vencido@test.example.com", plan_vence_at_days=-30)
    antes = utc_now()
    body = (await client.post(f"{BASE}/registrar", json=_pago(vencido), headers=auth_header(admin))).json()
    assert antes <= _dt(body["periodo_inicio"]) <= utc_now()


async def test_una_oferta_cobra_menos_sin_tocar_el_precio_del_plan(client, admin, user):
    response = await client.post(f"{BASE}/registrar", json=_pago(user, monto="60"), headers=auth_header(admin))
    assert response.status_code == 201
    assert response.json()["monto"] == "60.00"
    assert response.json()["plan"]["precio"] == "80.00"

    response = await client.post(f"{BASE}/registrar", json=_pago(user, monto="80.01"), headers=auth_header(admin))
    assert response.status_code == 422
    assert response.json()["details"] == {"monto": "No puede superar el precio del plan (80.00 USD)."}


async def test_referencias_invalidas_responden_422(client, admin, user):
    for body, field in (
        (_pago(user, plan_id=str(PLAN_FREE_ID)), "plan_id"),
        (_pago(user, plan_id=str(uuid4())), "plan_id"),
        ({**_pago(user), "user_id": str(uuid4())}, "user_id"),
    ):
        response = await client.post(f"{BASE}/registrar", json=body, headers=auth_header(admin))
        assert response.status_code == 422, body
        assert field in response.json()["details"]


async def test_datos_invalidos_responden_422(client, admin, user):
    for body in (
        _pago(user, moneda="USD"),  # la moneda la pone el plan
        _pago(user, periodo_fin="2030-01-01T00:00:00Z"),
        _pago(user, monto="-5"),
        _pago(user, metodo="cripto"),
        _pago(user, comprobante_url="http://inseguro.example.com/c.jpg"),
        {k: v for k, v in _pago(user).items() if k != "idempotency_key"},
    ):
        response = await client.post(f"{BASE}/registrar", json=body, headers=auth_header(admin))
        assert response.status_code == 422, body


async def test_un_reintento_con_la_misma_clave_no_cobra_dos_veces(client, admin, user):
    body = _pago(user)
    primero = (await client.post(f"{BASE}/registrar", json=body, headers=auth_header(admin))).json()
    segundo = await client.post(f"{BASE}/registrar", json=body, headers=auth_header(admin))
    assert segundo.json()["id"] == primero["id"]
    assert _dt((await _me(client, user))["plan_vence_at"]) == _dt(primero["periodo_fin"])

    # La misma clave para otro pago: 409.
    response = await client.post(
        f"{BASE}/registrar", json={**body, "plan_id": PLAN_BUSINESS_ID}, headers=auth_header(admin)
    )
    assert response.status_code == 409


# ---------- Anular ----------

async def test_anular_inserta_el_reverso_y_devuelve_el_plan_anterior(client, admin, user):
    vence_free = user.plan_vence_at
    pago = (await client.post(f"{BASE}/registrar", json=_pago(user), headers=auth_header(admin))).json()

    response = await client.post(f"{BASE}/{pago['id']}/anular", headers=auth_header(admin))
    assert response.status_code == 200
    reverso = response.json()
    assert (reverso["monto"], reverso["reverses_id"]) == ("-80.00", pago["id"])
    assert reverso["idempotency_key"] == f"reverso:{pago['id']}"

    # El original no se toca (kardex) y el usuario vuelve al free con su vencimiento anterior.
    original = (await client.get(f"{BASE}/{pago['id']}", headers=auth_header(admin))).json()
    assert original["monto"] == "80.00"
    me = await _me(client, user)
    assert me["plan_id"] == str(PLAN_FREE_ID)
    assert _dt(me["plan_vence_at"]) == vence_free


async def test_anular_un_pago_anterior_conserva_el_plan_del_ultimo(client, admin, user):
    pro = (await client.post(f"{BASE}/registrar", json=_pago(user), headers=auth_header(admin))).json()
    business = (
        await client.post(f"{BASE}/registrar", json=_pago(user, plan_id=PLAN_BUSINESS_ID), headers=auth_header(admin))
    ).json()
    await client.post(f"{BASE}/{pro['id']}/anular", headers=auth_header(admin))
    me = await _me(client, user)
    assert me["plan_id"] == PLAN_BUSINESS_ID
    assert _dt(me["plan_vence_at"]) == _dt(business["periodo_fin"]) - timedelta(days=365)


async def test_no_se_anula_dos_veces_ni_un_reverso(client, admin, user):
    pago = (await client.post(f"{BASE}/registrar", json=_pago(user), headers=auth_header(admin))).json()
    reverso = (await client.post(f"{BASE}/{pago['id']}/anular", headers=auth_header(admin))).json()
    for pago_id in (pago["id"], reverso["id"]):
        response = await client.post(f"{BASE}/{pago_id}/anular", headers=auth_header(admin))
        assert response.status_code == 409
        assert response.json()["code"] == "CONFLICT"


# ---------- Lectura, permisos y 404 ----------

async def test_el_listado_filtra_por_usuario_y_trae_sus_referencias(client, db_session, admin, user):
    otro = await create_usuario(db_session, "otro@test.example.com")
    await client.post(f"{BASE}/registrar", json=_pago(user), headers=auth_header(admin))
    await client.post(f"{BASE}/registrar", json=_pago(otro), headers=auth_header(admin))

    body = (await client.get(f"{BASE}/?user_id={user.id}", headers=auth_header(admin))).json()
    assert body["total"] == 1
    assert body["data"][0]["user"] == {"id": str(user.id), "email": user.email}
    assert body["data"][0]["plan"] == {"id": str(PLAN_PRO_ID), "nombre": "Pro"}


async def test_el_user_no_ve_ni_registra_pagos(client, admin, user):
    pago = (await client.post(f"{BASE}/registrar", json=_pago(user), headers=auth_header(admin))).json()
    headers = auth_header(user)
    for method, url, body in (
        ("GET", f"{BASE}/", None),
        ("GET", f"{BASE}/{pago['id']}", None),
        ("GET", f"{BASE}/{pago['id']}/audit", None),
        ("POST", f"{BASE}/registrar", _pago(user)),
        ("POST", f"{BASE}/{pago['id']}/anular", None),
    ):
        response = await client.request(method, url, json=body, headers=headers)
        assert response.status_code == 403, (method, url)


async def test_el_superadmin_tambien_registra_y_anula(client, superadmin, user):
    pago = await client.post(f"{BASE}/registrar", json=_pago(user), headers=auth_header(superadmin))
    assert pago.status_code == 201
    assert (await client.post(f"{BASE}/{pago.json()['id']}/anular", headers=auth_header(superadmin))).status_code == 200


async def test_pago_inexistente_responde_404(client, admin):
    for method, url in (
        ("GET", f"{BASE}/{uuid4()}"),
        ("GET", f"{BASE}/{uuid4()}/audit"),
        ("POST", f"{BASE}/{uuid4()}/anular"),
    ):
        assert (await client.request(method, url, headers=auth_header(admin))).status_code == 404, url


async def test_no_hay_rutas_para_editar_ni_borrar(client, admin, user):
    pago = (await client.post(f"{BASE}/registrar", json=_pago(user), headers=auth_header(admin))).json()
    assert (await client.patch(f"{BASE}/{pago['id']}", json={}, headers=auth_header(admin))).status_code == 405
    assert (await client.delete(f"{BASE}/{pago['id']}", headers=auth_header(admin))).status_code == 405
