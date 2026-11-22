from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from pydantic import Field

from app.domains.auth.schemas import CurrentUser
from app.domains.error_logs.models import ErrorLog
from app.middlewares.exception_handlers import register_exception_handlers
from app.shared.enums import Role
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.base import SchemaBase
from tests.conftest import make_settings


class FakeSession:
    """Sesión falsa: registra lo que se agrega y si hubo commit."""

    saved: list[object] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def add(self, obj):
        FakeSession.saved.append(obj)

    async def commit(self):
        FakeSession.saved.append("commit")


class Body(SchemaBase):
    nombre: str = Field(max_length=3)


def build_app(environment: str) -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app, make_settings(ENVIRONMENT=environment))
    app.state.db_session_factory = FakeSession
    app.state.test_user_id = uuid4()

    @app.get("/app-error")
    async def app_error():
        raise AppException("No autenticado.", 401, ErrorCode.TOKEN_REQUIRED)

    @app.post("/validation")
    async def validation(body: Body):
        return body

    @app.get("/http-error")
    async def http_error():
        raise HTTPException(status_code=404, detail="No existe.")

    @app.get("/boom")
    async def boom(request: Request):
        request.state.user = CurrentUser(id=request.app.state.test_user_id, role=Role.ADMIN)
        raise RuntimeError("fallo interno")

    return app


async def send(app: FastAPI, method: str, url: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, url, **kwargs)


@pytest.fixture(autouse=True)
def reset_saved():
    FakeSession.saved = []


async def test_app_exception_401_lleva_www_authenticate():
    response = await send(build_app("staging"), "GET", "/app-error")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {
        "status": "fail",
        "code": "TOKEN_REQUIRED",
        "message": "No autenticado.",
        "details": {},
    }


async def test_validacion_traduce_mensajes():
    response = await send(build_app("staging"), "POST", "/validation", json={"nombre": "Anastasia", "extra": 1})
    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"]["nombre"] == "El texto no debe superar 3 caracteres."
    assert body["details"]["extra"] == "Campo no permitido."


async def test_http_exception_usa_codigo_http():
    response = await send(build_app("staging"), "GET", "/http-error")
    assert response.status_code == 404
    assert response.json()["code"] == "HTTP_404"


async def test_error_inesperado_fuera_de_debug_guarda_error_log():
    app = build_app("staging")
    response = await send(app, "GET", "/boom")
    assert response.status_code == 500
    assert response.json() == {
        "status": "error",
        "code": "INTERNAL_ERROR",
        "message": "Ocurrió un error interno.",
        "details": {},
    }
    error_log, commit = FakeSession.saved
    assert isinstance(error_log, ErrorLog)
    assert error_log.user_id == app.state.test_user_id
    assert error_log.path == "/boom"
    assert commit == "commit"


async def test_error_inesperado_en_debug_expone_el_stack_y_no_guarda():
    response = await send(build_app("development"), "GET", "/boom")
    assert response.status_code == 500
    assert "stack" in response.json()["details"]
    assert FakeSession.saved == []
