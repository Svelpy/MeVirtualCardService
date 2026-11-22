from datetime import timedelta
from typing import Annotated
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Request

from app.core.config import get_settings
from app.core.security import create_access_token
from app.domains.auth.dependencies import get_current_principal_optional, require_permission, require_role
from app.domains.auth.schemas import CurrentUser
from app.middlewares.exception_handlers import register_exception_handlers
from app.shared.enums import Action, Module, Role
from tests.conftest import make_settings

SETTINGS = make_settings(ENVIRONMENT="staging")
USER_ID = uuid4()


def token(role: Role, expires: timedelta | None = None) -> str:
    return create_access_token({"sub": str(USER_ID), "role": role.value}, SETTINGS, expires)


def build_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, SETTINGS)
    app.dependency_overrides[get_settings] = lambda: SETTINGS

    @app.get("/leer")
    async def leer(
        request: Request,
        actor: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.READ))],
    ):
        return {"id": str(actor.id), "role": actor.role, "state": str(request.state.user.id)}

    @app.get("/crear")
    async def crear(actor: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.CREATE))]):
        return {"ok": True}

    @app.get("/solo-superadmin")
    async def solo_superadmin(actor: Annotated[CurrentUser, Depends(require_role(Role.SUPERADMIN))]):
        return {"ok": True}

    @app.get("/publico")
    async def publico(actor: Annotated[CurrentUser | None, Depends(get_current_principal_optional)]):
        return {"autenticado": actor is not None}

    return app


async def get(url: str, bearer: str | None = None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
    transport = httpx.ASGITransport(app=build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(url, headers=headers)


async def test_con_permiso_construye_el_actor_desde_el_token():
    response = await get("/leer", token(Role.ADMIN))
    assert response.status_code == 200
    assert response.json() == {"id": str(USER_ID), "role": "ADMIN", "state": str(USER_ID)}


async def test_sin_la_accion_responde_403():
    response = await get("/crear", token(Role.ADMIN))
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_sin_token_responde_401():
    response = await get("/leer")
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_REQUIRED"
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_token_invalido_o_vencido_responde_401():
    for bearer in ("no-es-un-jwt", token(Role.ADMIN, expires=timedelta(seconds=-1))):
        response = await get("/leer", bearer)
        assert response.status_code == 401
        assert response.json()["code"] == "TOKEN_INVALID"


async def test_require_role():
    assert (await get("/solo-superadmin", token(Role.SUPERADMIN))).status_code == 200
    assert (await get("/solo-superadmin", token(Role.ADMIN))).status_code == 403


async def test_principal_opcional():
    assert (await get("/publico")).json() == {"autenticado": False}
    assert (await get("/publico", token(Role.ADMIN))).json() == {"autenticado": True}
