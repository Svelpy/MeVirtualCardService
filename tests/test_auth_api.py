"""API de auth contra la base de desarrollo, dentro de una transacción revertida."""

import re

from sqlalchemy import select

from app.core.config import get_settings
from app.domains.auth.models import AuthSession
from tests.conftest import PASSWORD, PLAN_FREE_ID, auth_header, create_usuario


BASE = "/api/v1/auth"
COOKIE = get_settings().REFRESH_TOKEN_COOKIE_NAME


def _token_from(email: dict) -> str:
    return re.search(r"token=([\w-]+)", email["text"]).group(1)


async def _login(client, email: str, password: str = PASSWORD):
    return await client.post(f"{BASE}/login", json={"email": email, "password": password})


async def _refresh(client, csrf_token: str | None, refresh_token: str | None = None):
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    if refresh_token is not None:
        client.cookies.clear()
        headers["Cookie"] = f"{COOKIE}={refresh_token}"
    return await client.post(f"{BASE}/refresh", headers=headers)


# ---------- Registro y verificación ----------

async def test_registro_crea_un_user_free_sin_verificar_y_envia_el_enlace(client, sent_emails):
    response = await client.post(f"{BASE}/register", json={"email": "Ana@Test.Example.com", "password": PASSWORD})
    assert response.status_code == 201
    body = response.json()
    assert (body["email"], body["rol"], body["plan"]["id"]) == ("ana@test.example.com", "user", str(PLAN_FREE_ID))
    assert body["email_verified_at"] is None
    assert [email["to"] for email in sent_emails] == ["ana@test.example.com"]

    token = _token_from(sent_emails[0])
    assert (await client.post(f"{BASE}/verify-email", json={"token": token})).status_code == 204
    login = await _login(client, "ana@test.example.com")
    me = await client.get("/api/v1/usuarios/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["email_verified_at"] is not None

    # Un solo uso.
    response = await client.post(f"{BASE}/verify-email", json={"token": token})
    assert response.status_code == 422
    assert "token" in response.json()["details"]


async def test_registro_rechaza_email_repetido_y_datos_invalidos(client, user):
    response = await client.post(f"{BASE}/register", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 409
    for body in (
        {"email": "x@test.example.com", "password": "corta"},
        {"email": "no-es-email", "password": PASSWORD},
        {"email": "x@test.example.com", "password": PASSWORD, "rol": "admin"},
    ):
        assert (await client.post(f"{BASE}/register", json=body)).status_code == 422, body


async def test_reenviar_verificacion_invalida_el_enlace_anterior(client, db_session, sent_emails):
    pendiente = await create_usuario(db_session, "pendiente@test.example.com", verified=False)
    headers = auth_header(pendiente)
    assert (await client.post(f"{BASE}/resend-verification", headers=headers)).status_code == 204
    primero = _token_from(sent_emails[-1])
    assert (await client.post(f"{BASE}/resend-verification", headers=headers)).status_code == 204
    segundo = _token_from(sent_emails[-1])

    assert (await client.post(f"{BASE}/verify-email", json={"token": primero})).status_code == 422
    assert (await client.post(f"{BASE}/verify-email", json={"token": segundo})).status_code == 204
    # Ya verificado: 409.
    assert (await client.post(f"{BASE}/resend-verification", headers=headers)).status_code == 409


async def test_reenviar_verificacion_exige_sesion(client):
    assert (await client.post(f"{BASE}/resend-verification")).status_code == 401


# ---------- Login ----------

async def test_login_devuelve_tokens_y_deja_el_refresh_en_una_cookie_httponly(client, user):
    response = await _login(client, "USER@test.example.com")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "csrf_token", "token_type"}
    cookie = response.headers["set-cookie"]
    assert f"{COOKIE}=" in cookie and "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie
    me = await client.get("/api/v1/usuarios/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["id"] == str(user.id)


async def test_login_con_credenciales_incorrectas_responde_401_sin_revelar_el_email(client, user):
    wrong_password = await _login(client, user.email, "OtraClave999")
    unknown_email = await _login(client, "nadie@test.example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["code"] == "AUTHENTICATION_FAILED"


async def test_login_de_una_cuenta_dada_de_baja_responde_403(client, db_session):
    await create_usuario(db_session, "baja@test.example.com", is_active=False)
    response = await _login(client, "baja@test.example.com")
    assert response.status_code == 403


async def test_login_con_datos_invalidos_responde_422(client):
    for body in ({"email": "x@test.example.com"}, {"email": "x", "password": "x"}, {"email": "x@test.example.com", "password": ""}):
        assert (await client.post(f"{BASE}/login", json=body)).status_code == 422, body


# ---------- Refresh y logout ----------

async def test_refresh_exige_el_csrf_token_y_rota_la_sesion(client, user):
    login = (await _login(client, user.email)).json()
    old_refresh = client.cookies.get(COOKIE)

    assert (await _refresh(client, None)).status_code == 403
    assert (await _refresh(client, "csrf-falso")).json()["code"] == "CSRF_INVALID"

    response = await _refresh(client, login["csrf_token"])
    assert response.status_code == 200
    new_refresh = client.cookies.get(COOKIE)
    assert new_refresh != old_refresh
    assert response.json()["csrf_token"] != login["csrf_token"]


async def test_reusar_un_refresh_token_rotado_revoca_toda_la_familia(client, db_session, user):
    login = (await _login(client, user.email)).json()
    old_refresh = client.cookies.get(COOKIE)
    rotated = (await _refresh(client, login["csrf_token"])).json()
    new_refresh = client.cookies.get(COOKIE)

    # Alguien usa el token viejo: 401 y cae también la sesión vigente.
    response = await _refresh(client, login["csrf_token"], refresh_token=old_refresh)
    assert response.status_code == 401
    assert response.json()["code"] == "REFRESH_FAILED"
    assert (await _refresh(client, rotated["csrf_token"], refresh_token=new_refresh)).status_code == 401

    reasons = (await db_session.execute(select(AuthSession.revocation_reason).where(AuthSession.user_id == user.id))).scalars()
    assert sorted(reasons) == ["reuse_detected", "rotated"]


async def test_refresh_sin_cookie_o_de_un_usuario_dado_de_baja_responde_401(client, db_session, user, admin):
    client.cookies.clear()
    assert (await _refresh(client, "x")).status_code == 401

    login = (await _login(client, user.email)).json()
    await client.post(f"/api/v1/usuarios/{user.id}/dar-de-baja", headers=auth_header(admin))
    assert (await _refresh(client, login["csrf_token"])).status_code == 401


async def test_logout_revoca_la_sesion_y_borra_la_cookie(client, user):
    login = (await _login(client, user.email)).json()
    refresh_token = client.cookies.get(COOKIE)
    response = await client.post(f"{BASE}/logout")
    assert response.status_code == 204
    assert f'{COOKIE}=""' in response.headers["set-cookie"] or "Max-Age=0" in response.headers["set-cookie"]
    assert (await _refresh(client, login["csrf_token"], refresh_token=refresh_token)).status_code == 401
    # Sin cookie también responde 204.
    assert (await client.post(f"{BASE}/logout")).status_code == 204


# ---------- Contraseña ----------

async def test_recuperar_la_contrasena(client, user, sent_emails):
    # Un email que no existe responde igual y no envía nada.
    assert (await client.post(f"{BASE}/forgot-password", json={"email": "nadie@test.example.com"})).status_code == 204
    assert sent_emails == []

    login = (await _login(client, user.email)).json()
    refresh_token = client.cookies.get(COOKIE)
    assert (await client.post(f"{BASE}/forgot-password", json={"email": user.email})).status_code == 204
    token = _token_from(sent_emails[-1])

    response = await client.post(f"{BASE}/reset-password", json={"token": token, "new_password": "NuevaClave456"})
    assert response.status_code == 204
    assert (await _login(client, user.email)).status_code == 401
    assert (await _login(client, user.email, "NuevaClave456")).status_code == 200
    # Cierra las sesiones abiertas y el token sirve una sola vez.
    assert (await _refresh(client, login["csrf_token"], refresh_token=refresh_token)).status_code == 401
    response = await client.post(f"{BASE}/reset-password", json={"token": token, "new_password": "OtraClave789"})
    assert response.status_code == 422


async def test_restablecer_con_un_token_invalido_o_una_contrasena_debil_responde_422(client):
    assert (await client.post(f"{BASE}/reset-password", json={"token": "x", "new_password": "NuevaClave456"})).status_code == 422
    assert (await client.post(f"{BASE}/reset-password", json={"token": "x", "new_password": "corta"})).status_code == 422


async def test_cambiar_la_contrasena_cierra_las_otras_sesiones(client, user):
    otra = (await _login(client, user.email)).json()
    otra_refresh = client.cookies.get(COOKIE)

    response = await client.post(
        f"{BASE}/change-password",
        json={"current_password": "Incorrecta1", "new_password": "NuevaClave456"},
        headers=auth_header(user),
    )
    assert response.status_code == 401
    assert response.json()["details"] == {"current_password": "No coincide."}

    response = await client.post(
        f"{BASE}/change-password",
        json={"current_password": PASSWORD, "new_password": "NuevaClave456"},
        headers=auth_header(user),
    )
    assert response.status_code == 200
    nueva = response.json()
    assert (await _refresh(client, otra["csrf_token"], refresh_token=otra_refresh)).status_code == 401
    client.cookies.clear()
    assert (await _login(client, user.email, "NuevaClave456")).status_code == 200
    assert nueva["access_token"]


async def test_cambiar_la_contrasena_exige_sesion_y_datos_validos(client, user):
    body = {"current_password": PASSWORD, "new_password": "NuevaClave456"}
    assert (await client.post(f"{BASE}/change-password", json=body)).status_code == 401
    response = await client.post(
        f"{BASE}/change-password", json={**body, "new_password": "corta"}, headers=auth_header(user)
    )
    assert response.status_code == 422


# ---------- /auth/token: el formulario OAuth2 del botón Authorize de Swagger ----------

async def test_el_formulario_oauth2_inicia_sesion_como_el_login(client, user):
    response = await client.post(f"{BASE}/token", data={"username": user.email, "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert f"{COOKIE}=" in response.headers["set-cookie"]
    me = await client.get("/api/v1/usuarios/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["id"] == str(user.id)


async def test_el_formulario_oauth2_responde_401_y_422_como_el_login(client, user):
    response = await client.post(f"{BASE}/token", data={"username": user.email, "password": "OtraClave999"})
    assert response.status_code == 401
    response = await client.post(f"{BASE}/token", data={"username": "no-es-email", "password": PASSWORD})
    assert response.status_code == 422
    assert "username" in response.json()["details"]  # con el nombre de campo del formulario
    assert (await client.post(f"{BASE}/token", json={"email": user.email, "password": PASSWORD})).status_code == 422


def test_swagger_autoriza_contra_el_formulario_oauth2():
    from app.main import app

    flows = app.openapi()["components"]["securitySchemes"]["BearerAuth"]["flows"]
    assert flows["password"]["tokenUrl"] == "api/v1/auth/token"
