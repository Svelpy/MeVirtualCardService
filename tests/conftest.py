"""
Fixtures comunes.

Los tests de API corren contra la base de desarrollo (TEST_DATABASE_URL), que
comparten desarrollo, pruebas y staging (AGENTS.md §7). Por eso cada test corre
dentro de una transacción que se revierte al terminar: los commit de los
services se convierten en savepoints y ninguna fila queda en la base.
"""

import importlib
import pkgutil
from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

import app.domains
from app.core.base_model import utc_now
from app.core.config import Settings, get_settings
from app.core.database import create_database_engine, get_db
from app.core.security import create_access_token, hash_password
from app.domains.usuario.models import Usuario
from app.shared.enums import Role


# Todos los models, como en migrations/env.py: los Relationship() escritos como
# texto se resuelven al configurar los mappers, y un model sin importar los deja
# rotos para el resto de la sesión de tests.
for _module in pkgutil.iter_modules(app.domains.__path__):
    if (Path(app.domains.__path__[0]) / _module.name / "models.py").exists():
        importlib.import_module(f"app.domains.{_module.name}.models")

PLAN_FREE_ID = UUID("7b1e9c40-0000-4000-8000-000000000001")
PLAN_PRO_ID = UUID("7b1e9c40-0000-4000-8000-000000000002")
PASSWORD = "ClaveSegura123"


def make_settings(**overrides: object) -> Settings:
    """Settings de prueba que no leen el .env."""
    values: dict[str, object] = {
        "_env_file": None,
        "SECRET_KEY": "s" * 32,
        "CSRF_SECRET_KEY": "c" * 32,
        "PROD_ORIGINS": "https://app.example.com",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(scope="session")
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_database_engine(get_settings())
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session_factory(db_engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield factory
        finally:
            await transaction.rollback()


@pytest.fixture
async def db_session(db_session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Sesión para preparar datos y comprobar resultados desde el test."""
    async with db_session_factory() as session:
        yield session


class SentEmails(list):
    """Correos que la aplicación habría enviado con Resend."""


@pytest.fixture
def sent_emails(monkeypatch: pytest.MonkeyPatch) -> SentEmails:
    from app.integrations.resend import ResendService

    emails = SentEmails()

    async def fake_send_email(settings: Settings, **params: object) -> str:
        emails.append(params)
        return f"email-{len(emails)}"

    monkeypatch.setattr(ResendService, "send_email", staticmethod(fake_send_email))
    return emails


class CloudinaryCalls:
    """Lo que la aplicación habría hecho en Cloudinary."""

    def __init__(self) -> None:
        self.uploaded: list[str] = []
        self.confirmed: dict[str, str] = {}
        self.deleted: list[str] = []
        # Limpieza de huérfanas: lo que devuelve la API y lo que se le pidió.
        self.pending: list[dict[str, str]] = []
        self.deleted_ids: list[str] = []
        self.untagged_ids: list[str] = []


def uploaded_image_url(name: str | None = None) -> str:
    """Una URL con la forma exacta de las que devuelve POST /imagenes/uploads."""
    settings = get_settings()
    return (
        f"https://res.cloudinary.com/{settings.CLOUDINARY_CLOUD_NAME}/image/upload/v1700000000/"
        f"{settings.CLOUDINARY_FOLDER_NAME}/imagenes/{name or uuid4().hex}.jpg"
    )


@pytest.fixture
def cloudinary(monkeypatch: pytest.MonkeyPatch) -> CloudinaryCalls:
    from app.integrations.cloudinary import CloudinaryService

    calls = CloudinaryCalls()

    async def fake_upload_pending(file: object, settings: Settings) -> dict[str, str]:
        url = uploaded_image_url()
        calls.uploaded.append(url)
        return {"url": url, "public_id": url.rsplit("/", 1)[-1]}

    async def fake_confirm_pending_uploads(destinations: dict[str, str], settings: Settings) -> None:
        calls.confirmed.update(destinations)

    async def fake_safe_delete_image(image_url: str) -> bool:
        calls.deleted.append(image_url)
        return True

    async def fake_list_pending_uploads(settings: Settings, created_before: object) -> list[dict[str, str]]:
        return list(calls.pending)

    async def fake_delete_images(public_ids: list[str]) -> None:
        calls.deleted_ids.extend(public_ids)

    async def fake_remove_pending_tag(public_ids: list[str]) -> None:
        calls.untagged_ids.extend(public_ids)

    monkeypatch.setattr(CloudinaryService, "list_pending_uploads", staticmethod(fake_list_pending_uploads))
    monkeypatch.setattr(CloudinaryService, "delete_images", staticmethod(fake_delete_images))
    monkeypatch.setattr(CloudinaryService, "remove_pending_tag", staticmethod(fake_remove_pending_tag))
    monkeypatch.setattr(CloudinaryService, "upload_pending", staticmethod(fake_upload_pending))
    monkeypatch.setattr(CloudinaryService, "confirm_pending_uploads", staticmethod(fake_confirm_pending_uploads))
    monkeypatch.setattr(CloudinaryService, "safe_delete_image", staticmethod(fake_safe_delete_image))
    return calls


@pytest.fixture
async def client(
    db_session_factory: async_sessionmaker[AsyncSession],
    sent_emails: SentEmails,
    cloudinary: CloudinaryCalls,
) -> AsyncIterator[httpx.AsyncClient]:
    from app.main import app
    from app.middlewares.limiter import limiter

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    previous_factory = getattr(app.state, "db_session_factory", None)
    app.state.db_session_factory = db_session_factory
    limiter.enabled = False
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
            yield http_client
    finally:
        limiter.enabled = True
        app.state.db_session_factory = previous_factory
        app.dependency_overrides.clear()


async def create_usuario(
    db_session: AsyncSession,
    email: str,
    *,
    rol: Role = Role.USER,
    password: str = PASSWORD,
    verified: bool = True,
    is_active: bool = True,
    plan_id: UUID = PLAN_FREE_ID,
    plan_vence_at_days: int = 7,
) -> Usuario:
    usuario = Usuario(
        email=email,
        password_hash=hash_password(password),
        rol=rol,
        plan_id=plan_id,
        plan_vence_at=utc_now() + timedelta(days=plan_vence_at_days),
        is_active=is_active,
        email_verified_at=utc_now() if verified else None,
    )
    db_session.add(usuario)
    await db_session.commit()
    return usuario


def auth_header(usuario: Usuario) -> dict[str, str]:
    token = create_access_token({"sub": str(usuario.id), "role": usuario.rol.value}, get_settings())
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def superadmin(db_session: AsyncSession) -> Usuario:
    return await create_usuario(db_session, "superadmin@test.example.com", rol=Role.SUPERADMIN)


@pytest.fixture
async def admin(db_session: AsyncSession) -> Usuario:
    return await create_usuario(db_session, "admin@test.example.com", rol=Role.ADMIN)


@pytest.fixture
async def user(db_session: AsyncSession) -> Usuario:
    return await create_usuario(db_session, "user@test.example.com")
