"""API de usuario (Raíz) contra la base de desarrollo, dentro de una transacción revertida."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.security import hash_refresh_token
from app.domains.auth.models import AuthSession, EmailVerificationToken
from app.domains.pago.models import Pago
from app.domains.tarjeta.models import Tarjeta
from app.shared.enums import MetodoPago, Role
from tests.conftest import PLAN_FREE_ID, PLAN_PRO_ID, auth_header, create_usuario


BASE = "/api/v1/usuarios"


async def _add_tarjeta(db_session, usuario, *, is_public: bool = True) -> Tarjeta:
    tarjeta = Tarjeta(
        user_id=usuario.id,
        slug=f"t-{uuid4().hex[:8]}",
        rubro="Pediatría",
        nombres="Ana",
        is_public=is_public,
        published_at=utc_now() if is_public else None,
    )
    db_session.add(tarjeta)
    await db_session.commit()
    return tarjeta


async def _add_session(db_session, usuario) -> AuthSession:
    session = AuthSession(
        user_id=usuario.id,
        refresh_token_hash=hash_refresh_token(uuid4().hex),
        expires_at=utc_now() + timedelta(days=7),
    )
    db_session.add(session)
    await db_session.commit()
    return session


# ---------- /me ----------

async def test_me_devuelve_el_usuario_con_su_plan_y_sin_password(client, user):
    response = await client.get(f"{BASE}/me", headers=auth_header(user))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["plan"]["codigo"] == "free"
    assert "password_hash" not in body and "created_by" not in body


async def test_me_cambiar_el_email_lo_deja_sin_verificar_y_revoca_los_enlaces(client, db_session, user):
    token = EmailVerificationToken(
        user_id=user.id, token_hash=hash_refresh_token("t"), expires_at=utc_now() + timedelta(hours=1)
    )
    db_session.add(token)
    await db_session.commit()

    response = await client.patch(f"{BASE}/me", json={"email": "  Nuevo@Test.Example.com "}, headers=auth_header(user))
    assert response.status_code == 200
    assert response.json()["email"] == "nuevo@test.example.com"
    assert response.json()["email_verified_at"] is None
    await db_session.refresh(token)
    assert token.revoked_at is not None


async def test_me_no_acepta_rol_ni_un_email_ajeno(client, user, admin):
    response = await client.patch(f"{BASE}/me", json={"rol": "superadmin"}, headers=auth_header(user))
    assert response.status_code == 422
    response = await client.patch(f"{BASE}/me", json={"email": admin.email}, headers=auth_header(user))
    assert response.status_code == 409
    assert response.json()["details"] == {"email": "Ya está registrado."}


async def test_me_sin_token_responde_401(client):
    assert (await client.get(f"{BASE}/me")).status_code == 401


# ---------- Permisos (403) ----------

async def test_el_user_no_gestiona_usuarios(client, user, admin):
    headers = auth_header(user)
    requests = (
        ("GET", f"{BASE}/", None),
        ("GET", f"{BASE}/{admin.id}", None),
        ("GET", f"{BASE}/{admin.id}/audit", None),
        ("POST", f"{BASE}/", {"email": "x@test.example.com", "password": "ClaveSegura123"}),
        ("PATCH", f"{BASE}/{admin.id}", {"email": "x@test.example.com"}),
        ("DELETE", f"{BASE}/{admin.id}", None),
        ("POST", f"{BASE}/{admin.id}/dar-de-baja", None),
    )
    for method, url, body in requests:
        response = await client.request(method, url, json=body, headers=headers)
        assert response.status_code == 403, (method, url)


async def test_la_jerarquia_impide_gestionar_un_rol_igual_o_superior(client, db_session, admin, superadmin):
    otro_admin = await create_usuario(db_session, "admin2@test.example.com", rol=Role.ADMIN)
    headers = auth_header(admin)
    # Lo ve (READ), pero no puede modificarlo: 403, no 404 (§24).
    assert (await client.get(f"{BASE}/{superadmin.id}", headers=headers)).status_code == 200
    for method, url, body in (
        ("PATCH", f"{BASE}/{superadmin.id}", {"email": "x@test.example.com"}),
        ("PATCH", f"{BASE}/{otro_admin.id}", {"email": "x@test.example.com"}),
        ("PATCH", f"{BASE}/{admin.id}", {"rol": "user"}),  # nadie cambia su propio rol
        ("DELETE", f"{BASE}/{otro_admin.id}", None),
        ("POST", f"{BASE}/{otro_admin.id}/dar-de-baja", None),
        ("POST", f"{BASE}/", {"email": "x@test.example.com", "password": "ClaveSegura123", "rol": "admin"}),
    ):
        response = await client.request(method, url, json=body, headers=headers)
        assert response.status_code == 403, (method, url, body)
        assert response.json()["code"] == "PERMISSION_DENIED"


async def test_el_admin_no_asciende_a_un_user_y_el_superadmin_si(client, user, admin, superadmin):
    response = await client.patch(f"{BASE}/{user.id}", json={"rol": "admin"}, headers=auth_header(admin))
    assert response.status_code == 403
    response = await client.patch(f"{BASE}/{user.id}", json={"rol": "admin"}, headers=auth_header(superadmin))
    assert response.status_code == 200
    assert response.json()["rol"] == "admin"


# ---------- CRUD ----------

async def test_el_admin_crea_un_user_con_plan_free_y_sin_verificar(client, admin):
    response = await client.post(
        f"{BASE}/", json={"email": "Nuevo@Test.Example.com", "password": "ClaveSegura123"}, headers=auth_header(admin)
    )
    assert response.status_code == 201
    body = response.json()
    assert (body["email"], body["rol"], body["plan_id"]) == ("nuevo@test.example.com", "user", str(PLAN_FREE_ID))
    assert body["email_verified_at"] is None and body["is_active"] is True
    audit = (await client.get(f"{BASE}/{body['id']}/audit", headers=auth_header(admin))).json()
    assert audit["created_by"] == str(admin.id)


async def test_el_superadmin_crea_un_admin(client, superadmin):
    response = await client.post(
        f"{BASE}/",
        json={"email": "admin.nuevo@test.example.com", "password": "ClaveSegura123", "rol": "admin"},
        headers=auth_header(superadmin),
    )
    assert response.status_code == 201
    assert response.json()["rol"] == "admin"


async def test_el_listado_trae_el_plan_y_filtra(client, db_session, admin):
    await create_usuario(db_session, "pro@test.example.com", plan_id=PLAN_PRO_ID)
    await create_usuario(db_session, "baja@test.example.com", is_active=False)
    response = await client.get(f"{BASE}/?plan_id={PLAN_PRO_ID}", headers=auth_header(admin))
    assert response.status_code == 200
    emails = [u["email"] for u in response.json()["data"]]
    assert "pro@test.example.com" in emails
    assert all(u["plan"]["id"] == str(PLAN_PRO_ID) for u in response.json()["data"])

    response = await client.get(f"{BASE}/?is_active=false&rol=user", headers=auth_header(admin))
    assert "baja@test.example.com" in [u["email"] for u in response.json()["data"]]

    response = await client.get(f"{BASE}/?per_page=1", headers=auth_header(admin))
    body = response.json()
    assert len(body["data"]) == 1 and body["total_pages"] == body["total"]


async def test_email_duplicado_responde_409(client, admin, user):
    response = await client.post(
        f"{BASE}/", json={"email": user.email.upper(), "password": "ClaveSegura123"}, headers=auth_header(admin)
    )
    assert response.status_code == 409
    response = await client.patch(f"{BASE}/{user.id}", json={"email": admin.email}, headers=auth_header(admin))
    assert response.status_code == 409


async def test_datos_invalidos_responden_422(client, admin, user):
    headers = auth_header(admin)
    for body in (
        {"email": "no-es-email", "password": "ClaveSegura123"},
        {"email": "x@test.example.com", "password": "corta"},
        {"email": "x@test.example.com", "password": "ClaveSegura123", "rol": "dueño"},
        {"email": "x@test.example.com", "password": "ClaveSegura123", "plan_id": str(PLAN_PRO_ID)},
    ):
        assert (await client.post(f"{BASE}/", json=body, headers=headers)).status_code == 422, body
    for body in ({"email": None}, {"is_active": False}, {"password": "OtraClave123"}):
        assert (await client.patch(f"{BASE}/{user.id}", json=body, headers=headers)).status_code == 422, body
    assert (await client.get(f"{BASE}/no-es-uuid", headers=headers)).status_code == 422


async def test_usuario_inexistente_o_eliminado_responde_404(client, admin):
    headers = auth_header(admin)
    for method, url in (
        ("GET", f"{BASE}/{uuid4()}"),
        ("GET", f"{BASE}/{uuid4()}/audit"),
        ("PATCH", f"{BASE}/{uuid4()}"),
        ("DELETE", f"{BASE}/{uuid4()}"),
        ("POST", f"{BASE}/{uuid4()}/dar-de-baja"),
    ):
        response = await client.request(method, url, json={} if method == "PATCH" else None, headers=headers)
        assert response.status_code == 404, (method, url)


async def test_eliminar_es_logico_libera_el_email_y_queda_en_la_auditoria(client, db_session, admin, user):
    session = await _add_session(db_session, user)
    headers = auth_header(admin)
    assert (await client.delete(f"{BASE}/{user.id}", headers=headers)).status_code == 204

    assert (await client.get(f"{BASE}/{user.id}", headers=headers)).status_code == 404
    audit = (await client.get(f"{BASE}/{user.id}/audit", headers=headers)).json()
    assert audit["is_deleted"] is True and audit["deleted_by"] == str(admin.id)
    await db_session.refresh(session)
    assert session.revocation_reason == "user_deleted"

    # El índice único es parcial: el email queda libre.
    response = await client.post(f"{BASE}/", json={"email": user.email, "password": "ClaveSegura123"}, headers=headers)
    assert response.status_code == 201


async def test_eliminar_con_tarjeta_o_con_pagos_responde_409(client, db_session, admin):
    con_tarjeta = await create_usuario(db_session, "tarjeta@test.example.com")
    await _add_tarjeta(db_session, con_tarjeta)
    con_pago = await create_usuario(db_session, "pago@test.example.com")
    db_session.add(
        Pago(
            user_id=con_pago.id,
            plan_id=PLAN_PRO_ID,
            monto=Decimal("80.00"),
            moneda="USD",
            metodo=MetodoPago.QR,
            periodo_inicio=utc_now(),
            periodo_fin=utc_now() + timedelta(days=365),
            idempotency_key=uuid4().hex,
        )
    )
    await db_session.commit()

    for usuario in (con_tarjeta, con_pago):
        response = await client.delete(f"{BASE}/{usuario.id}", headers=auth_header(admin))
        assert response.status_code == 409
        assert response.json()["code"] == "CONFLICT"


# ---------- Acciones ----------

async def test_dar_de_baja_revoca_sesiones_y_despublica_y_reactivar_no_republica(client, db_session, admin, user):
    tarjeta = await _add_tarjeta(db_session, user)
    session = await _add_session(db_session, user)

    response = await client.post(f"{BASE}/{user.id}/dar-de-baja", headers=auth_header(admin))
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    await db_session.refresh(session)
    await db_session.refresh(tarjeta)
    assert session.revocation_reason == "user_deactivated"
    assert tarjeta.is_public is False

    # Repetirla no cambia nada.
    assert (await client.post(f"{BASE}/{user.id}/dar-de-baja", headers=auth_header(admin))).status_code == 200

    response = await client.post(f"{BASE}/{user.id}/reactivar", headers=auth_header(admin))
    assert response.status_code == 200
    assert response.json()["is_active"] is True
    await db_session.refresh(tarjeta)
    assert tarjeta.is_public is False


async def test_dar_de_baja_no_toca_otras_tarjetas(client, db_session, admin, user):
    otro = await create_usuario(db_session, "otro@test.example.com")
    tarjeta_ajena = await _add_tarjeta(db_session, otro)
    await client.post(f"{BASE}/{user.id}/dar-de-baja", headers=auth_header(admin))
    result = await db_session.execute(select(Tarjeta.is_public).where(Tarjeta.id == tarjeta_ajena.id))
    assert result.scalar_one() is True
