# ARCHITECTURE.md

Referencia ampliada de `AGENTS.md`. Explica el porqué de sus reglas, muestra
ejemplos completos y guarda el material de referencia (Dockerfile, plantillas,
migrations) que no cabe en las reglas.

Cómo se relacionan los dos documentos:

- **Misma numeración.** El §N de este archivo amplía el §N de `AGENTS.md`. Para
  ampliar una regla se lee solo la sección con su mismo número.
- **No define reglas nuevas.** Todo lo obligatorio está en `AGENTS.md`; aquí
  solo hay explicaciones, ejemplos y referencias. Si ambos documentos se
  contradicen, prevalece `AGENTS.md`.
- **Un ejemplo común.** Las secciones de la API (§17–§25) usan el mismo
  sistema de pedidos, para que cada ejemplo continúe el anterior.

---

## 1. Stack

Versiones fijadas en `requirements.txt`:

| Pieza | Paquete | Por qué |
|---|---|---|
| Lenguaje | Python 3.14 | Sintaxis de tipos moderna (`X \| None`, `Self`) y soporte de todas las dependencias |
| API | `fastapi`, `uvicorn[standard]` | Validación y OpenAPI a partir de los tipos; ASGI async |
| Base de datos | PostgreSQL | Índices parciales, triggers y `SELECT ... FOR UPDATE`, que usan las reglas de §19 |
| ORM | `sqlmodel` sobre `SQLAlchemy[asyncio]` 2.x | Models declarativos y sesión async |
| Driver | `asyncpg` | Driver async nativo de PostgreSQL |
| Schemas | `pydantic` 2 | Validación de entrada y salida |
| Configuración | `pydantic-settings` | `Settings` tipado a partir de variables de entorno |
| Migraciones | `alembic` | Versionado del esquema |
| JWT | `python-jose` | Firma HS256 de los access tokens |
| Contraseñas | `pwdlib[argon2]` | Argon2, el algoritmo que recomienda OWASP |
| HTTP saliente | `httpx` | Cliente async; `requests` bloquearía el event loop |
| Tests | `pytest`, `pytest-asyncio` | Tests async con `asyncio_mode = auto` |

**Por qué async.** Una API pasa la mayor parte del tiempo esperando a
PostgreSQL o a un proveedor externo. Con async, un mismo proceso atiende otras
peticiones durante esa espera. El costo es que la sesión no puede cargar
relaciones de forma implícita (§18).

**Por qué models y schemas no se heredan entre sí.** Un model describe la
tabla; un schema describe un contrato HTTP. Si uno hereda del otro:

- un campo interno, como `password_hash`, puede terminar en una respuesta;
- un cambio en la API obliga a una migration, y al revés;
- un endpoint no puede aceptar o devolver una forma distinta de la tabla.

La duplicación de algunos campos es el precio de mantener las dos capas
independientes.

---

## 2. Estructura de `app/`

```text
app/
├── api.py                     → agrega routers (§12)
├── main.py                    → compone la aplicación (§12)
├── core/
│   ├── base_model.py          → BaseModel con id y auditoría (§18)
│   ├── config.py              → Settings y get_settings (§6)
│   ├── database.py            → engine, sesiones y get_db (§7)
│   ├── logging.py             → setup_logging y get_logger (§9)
│   ├── openapi.py             → conserva los ejemplos de los schemas (§20)
│   ├── security.py            → primitivas de hashing, JWT, CSRF y tokens (§24)
│   └── system_router.py       → GET / y GET /health (§13)
├── domains/
│   ├── auth/                  → dependencies.py, models de sesiones y tokens; service y routes se construyen (§24)
│   ├── error_logs/            → ErrorLog y su repository (obligatorio)
│   └── <dominio>/
│       ├── models.py
│       ├── schemas.py
│       ├── repositories.py
│       ├── services.py
│       └── routes.py
├── integrations/              → un archivo por proveedor (§11)
├── middlewares/               → CORS, limiter y exception handlers (§10)
└── shared/
    ├── enums.py               → Role, Module, Action y enums del dominio
    ├── errors/
    │   ├── codes.py           → ErrorCode
    │   └── exceptions.py      → AppException
    ├── schemas/
    │   ├── base.py            → SchemaBase y AuditMixin (§20)
    │   ├── errors.py          → ErrorResponse, ERROR_RESPONSES y error_responses (§23)
    │   ├── pagination.py      → PaginatedResponse (§23)
    │   └── tree.py            → TreeResponse y TreeNodeResponse (§20)
    └── services/
        ├── permissions.py     → matriz de permisos y alcances (§24)
        ├── slug.py            → generate_slug
        ├── sync.py            → plan de sincronización de listas (§22)
        └── validators.py      → validadores object → T (§21)
```

Fuera de `app/`:

```text
database.md            → SQL de PostgreSQL del sistema; entrada de §25
migrations/            → Alembic (§8)
seeds/                 → datos iniciales que no son Filas fijas; se ejecutan a mano
tests/
AGENTS.md
ARCHITECTURE.md
```

---

## 3. Responsabilidades

### Dónde va cada cosa

```text
Infraestructura            → core/
Negocio                    → domains/
Proveedor externo          → integrations/
HTTP global                → middlewares/
Código entre dominios      → shared/
```

Dentro de un dominio:

| Archivo | Contiene | Nunca contiene |
|---|---|---|
| `models.py` | Tablas, columnas, índices, relaciones | Lógica HTTP o de negocio |
| `schemas.py` | Contratos de entrada y salida, validadores de campo | Queries, reglas de negocio |
| `repositories.py` | Queries, filtros, alcance, carga de relaciones | Reglas de negocio, `commit()` |
| `services.py` | Reglas de negocio, transacciones, auditoría | Queries SQL, respuestas HTTP |
| `routes.py` | HTTP: dependencias, parámetros, códigos de estado | Queries, SDKs externos |

### Flujo de una request

```text
HTTP → route → dependencias (auth, sesión) → schema de entrada
     → service → repository → PostgreSQL
     → service → commit y recarga → schema de salida → HTTP
```

Error esperado y error inesperado:

```text
service → AppException ─────────────→ handler → ErrorResponse 4xx
código  → Exception no controlada ──→ handler global → logger + ErrorLog → 500 genérico
```

### `auth/` y `error_logs/`

`auth/dependencies.py` expone las dependencias de autorización (§24):

```text
get_current_principal            → CurrentUser a partir del access token
get_current_principal_optional   → None si no hay token
require_permission(Module, Action)
require_role(*roles)
```

`oauth2_scheme` usa `auto_error=False`: el token es opcional en la capa de
OpenAPI y cada dependencia decide si exige o no autenticación.

`CurrentUser` se construye con el `sub` y el `role` del token, sin consultar la
base: los permisos funcionan sin ningún dominio de usuarios. Un cambio de rol o
una eliminación rige cuando vence el access token (10 a 15 minutos según
`ACCESS_TOKEN_EXPIRE_MINUTES`). Un proyecto que necesite revocar el acceso al
instante carga al usuario desde su repository en `get_current_principal`.

`auth/models.py` y los schemas de login, refresh y recuperación son la base del
dominio `auth` completo. `models.py` apunta a la tabla `usuario`: se importa en
`migrations/env.py` solo cuando ese dominio existe.

`error_logs/` no tiene routes ni schemas mientras no exista una API para
consultarlos. `ErrorLog` guarda `status`, `message`, `stack`, `path`, `method`,
`ip_address`, `user_agent` y `user_id`.

### Por qué no hay más capas

No se agregan controllers, managers, use cases, repositories genéricos ni
clases base de repository. Cada capa extra es un lugar más donde buscar la
lógica, y sin una necesidad real solo agrega indirección.

---

## 4. Imports entre capas

```text
routes ──→ services ──→ repositories ──→ models
  │           │
  │           └──→ integrations
  └──→ schemas ←── services
core y shared ←── cualquier capa
```

Por qué cada prohibición:

| Prohibido | Qué rompería |
|---|---|
| `models → services`, `models → routes` | Imports circulares al arrancar: todo importa los models |
| `repositories → services` | El repository dejaría de ser reutilizable por varios services |
| `services → routes` | El service dependería de HTTP y no podría usarse desde un job o un test |
| `routes → repositories` | La route se saltaría permisos, alcance y soft delete del service |
| `schemas → routes`, `integrations → routes` | Dependencias hacia arriba, sin ningún uso legítimo |

Cuando un repository necesita un tipo que también usa el service, el tipo se
define en el repository. Así lo hace el alcance de datos: `<Modulo>Scope` vive
en `repositories.py` y el service lo importa (§24).

Única excepción: `middlewares/exception_handlers.py` persiste `ErrorLog`
abriendo su propia sesión (§7), porque el handler global no pasa por ningún
service.

---

## 5. Imports y archivos `__init__.py`

Bloque de imports completo de un `routes.py`:

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.pedidos.schemas import PedidoResponseDetail
from app.domains.pedidos.services import PedidoService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses
```

Por qué cada regla:

- **Importar desde el archivo de origen.** Con una fachada en `__init__.py`,
  importar un dominio carga todos sus archivos, y es fácil crear un import
  circular sin verlo.
- **Imports absolutos.** `from .models import X` y
  `from app.domains.pedidos.models import X` cargan el mismo módulo de dos
  formas; con absolutos el origen se lee sin abrir el archivo.
- **Tres grupos ordenados.** Separa lo propio de lo externo y es el orden que
  aplican isort y ruff (`ruff check --select I --fix`).

`middlewares/__init__.py` es un ejemplo de excepción válida: define
`register_all_middlewares`, que no reexporta nada.

---

## 6. Config

`Settings` agrupa las variables por tema y deriva valores de `ENVIRONMENT`, para
que no puedan contradecirse (por ejemplo, `ENVIRONMENT=production` con
`DEBUG=true`):

| Propiedad derivada | Regla |
|---|---|
| `DEBUG` | `True` solo en `development` |
| `DOCS_ENABLED` | La variable si está definida; si no, igual a `DEBUG` |
| `CORS_ORIGINS_LIST` | `DEV_ORIGINS` en `development` y `test`; `PROD_ORIGINS` en el resto, obligatoria |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Una variable por entorno |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Una variable por entorno |
| `REFRESH_TOKEN_COOKIE_SECURE` | `True` en `staging` y `production` |
| `CLOUDINARY_FOLDER_NAME` | Carpeta de producción o de pruebas, obligatoria |

Validaciones al arrancar:

- `SECRET_KEY` y `CSRF_SECRET_KEY` tienen al menos 32 bytes y son distintas.
- Una variable vacía (`DOCS_ENABLED=`) equivale a no definirla.
- `extra="ignore"`: variables desconocidas del entorno no rompen el arranque.

En los tests, la configuración se reemplaza sin tocar el `.env`:

```python
app.dependency_overrides[get_settings] = lambda: Settings(ENVIRONMENT="test")
get_settings.cache_clear()
```

Esto solo funciona porque los módulos reciben `settings` por parámetro o por
`Depends(get_settings)`. Un `settings = get_settings()` a nivel de módulo
quedaría fijado al importarse.

---

## 7. Base de datos

### Selección de la base

| `ENVIRONMENT` | Variable | Contenido |
|---|---|---|
| `production` | `DATABASE_URL` | Datos reales |
| `development`, `test`, `staging` | `TEST_DATABASE_URL` | Base no productiva compartida |

La selección vive en `_get_database_url(settings)` y la reutiliza Alembic (§8),
para que una migration nunca se aplique a una base distinta de la que usa la
aplicación. Mientras los tres entornos no productivos compartan base, un test
no vacía tablas sin una protección explícita.

### Engine y sesiones

```python
create_async_engine(url, echo=settings.DEBUG, pool_pre_ping=True, connect_args=get_connect_args())
async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
```

| Opción | Por qué |
|---|---|
| `pool_pre_ping=True` | Descarta conexiones que el servidor o el pooler cerraron |
| `get_connect_args()` | Desactiva la caché de prepared statements de asyncpg y les da nombres únicos; necesario detrás de PgBouncer o de un pooler en modo transacción |
| `expire_on_commit=False` | Tras el commit los atributos siguen cargados; en async, recargarlos de forma implícita fallaría |
| `autoflush=False` | El service decide cuándo hacer `flush()` (§22) |

### Una sesión por request

```python
async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise RuntimeError("La fábrica de sesiones no está inicializada")
    async with session_factory() as session:
        yield session
```

FastAPI ejecuta una dependencia una sola vez por request: la autenticación y
la route comparten la misma sesión y la misma transacción. Al terminar, la
sesión se cierra y lo que no se confirmó se descarta.

### Sesiones fuera de `Depends()`

Una background task recibe ids y abre su propia sesión:

```python
async def enviar_comprobante(session_factory: async_sessionmaker[AsyncSession], pedido_id: UUID) -> None:
    async with session_factory() as session:
        pedido = await PedidoRepository.get(session, pedido_id, scope=PedidoScope(all=True))
        ...


background_tasks.add_task(enviar_comprobante, request.app.state.db_session_factory, pedido.id)
```

El handler global de errores hace lo mismo para guardar `ErrorLog`: si la
transacción de la request falló, su sesión puede estar inutilizable.

Una `AsyncSession` tampoco se comparte entre tareas concurrentes:

```python
# No: dos queries a la vez sobre la misma sesión
await asyncio.gather(ClienteRepository.get(s, a), ProductoRepository.get(s, b))
```

---

## 8. Alembic

### Configuración inicial

```bash
alembic init -t async migrations
```

`migrations/env.py`, modo online:

```python
import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

import app.domains.auth.models  # noqa: F401
import app.domains.error_logs.models  # noqa: F401
import app.domains.pedidos.models  # noqa: F401  (un import por dominio)
from app.core.config import get_settings
from app.core.database import _get_database_url, get_connect_args

target_metadata = SQLModel.metadata


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        _get_database_url(get_settings()),
        poolclass=pool.NullPool,
        connect_args=get_connect_args(),
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())
```

Un model que no se importa en `env.py` no está en `SQLModel.metadata`, y
autogenerate propondría eliminar su tabla.

Convención de nombres, en `core/base_model.py`, antes de declarar cualquier
model:

```python
SQLModel.metadata.naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

Sin ella, PostgreSQL inventa los nombres y una migration posterior no puede
eliminar el constraint sin conocerlo.

La regla `ck` ya agrega el prefijo y la tabla: un `CheckConstraint` recibe solo
la parte final del nombre.

```python
CheckConstraint("monto >= 0", name="monto_positivo")  # → ck_pagos_monto_positivo
```

`migrations/script.py.mako` agrega `import sqlmodel` junto a los imports de
Alembic, porque autogenerate escribe tipos como `sqlmodel.sql.sqltypes.AutoString`.

### Qué se escribe a mano

**Renombrar una columna** (autogenerate la eliminaría y crearía otra vacía):

```python
op.alter_column("clientes", "nombre", new_column_name="razon_social")
```

**Trigger de un Registro** (§19), en la migración inicial:

```python
def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION forbid_update_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'La tabla % solo admite INSERT', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER movimientos_insert_only
        BEFORE UPDATE OR DELETE ON movimientos
        FOR EACH ROW EXECUTE FUNCTION forbid_update_delete();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER movimientos_insert_only ON movimientos")
    op.execute("DROP FUNCTION forbid_update_delete()")
```

La función se crea una vez y la reutiliza el trigger de cada Registro.

**Filas fijas** (§17):

```python
monedas = sa.table(
    "monedas",
    sa.column("id", sa.Uuid),
    sa.column("codigo", sa.String),
    sa.column("orden", sa.Integer),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("is_deleted", sa.Boolean),
)
now = datetime.now(timezone.utc)
op.bulk_insert(monedas, [
    {"id": UUID("5f0c2c1e-0000-4000-8000-000000000001"), "codigo": "BOB", "orden": 1,
     "created_at": now, "updated_at": now, "is_deleted": False},
])
```

Los defaults de `BaseModel` se aplican en Python, no en la base: un
`bulk_insert` debe enviar `created_at`, `updated_at` e `is_deleted`.

### Comandos

```bash
alembic revision --autogenerate -m "agrega pedidos"
alembic upgrade head
alembic downgrade -1
alembic check        # falla si los models tienen cambios sin migration
```

---

## 9. Logging

```python
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
```

Uso esperado:

- `logger.info` para hechos operativos (arranque, conexión inicializada).
- `logger.exception` dentro de un `except`, para que el log incluya el stack.
- Nunca se registran contraseñas, tokens, secretos ni connection strings.
- `print` no se usa: no tiene nivel ni origen.

---

## 10. Middlewares

### Orden de registro

```python
register_exception_handlers(app, settings)
register_rate_limiter(app)
register_cors(app, settings)
```

Starlette ejecuta los middlewares en orden inverso al de registro: CORS, el
último registrado, es el primero en recibir la request. Así hasta un `429` o un
`500` lleva las cabeceras CORS y el navegador puede leer el error.

### CORS

```text
allow_origins      → settings.CORS_ORIGINS_LIST
allow_credentials  → True (la cookie del refresh token)
allow_methods      → GET, POST, PATCH, DELETE
allow_headers      → Authorization, Content-Type, Accept, Origin, X-Requested-With, X-CSRF-Token
```

Con `allow_credentials=True` los orígenes nunca pueden ser `*`.

### Limiter

```text
default_limits = 300/minute
storage_uri    = memory://
strategy       = fixed-window
key_func       = IP del cliente
```

Un endpoint público que recibe credenciales lleva su propio límite (§24). SlowAPI
exige el parámetro `request`:

```python
@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, data: UserLogin) -> TokenResponse: ...
```

`memory://` cuenta por proceso: con varias réplicas, cada una tiene su propio
contador. En ese caso se usa un almacenamiento compartido como Redis.

### Formato de errores

Todos los errores siguen `ErrorResponse`:

```json
{ "status": "fail", "code": "...", "message": "...", "details": {} }
```

| Origen | `status` | `code` | `details` |
|---|---|---|---|
| `AppException` | `fail` | El de la excepción | El de la excepción; un `401` agrega `WWW-Authenticate: Bearer` |
| `RequestValidationError` | `fail` | `VALIDATION_ERROR` | `{"campo -> subcampo": "mensaje en español"}` |
| `RateLimitExceeded` | `fail` | `HTTP_429` | Vacío; cabeceras `Retry-After` y `X-RateLimit-*` |
| `StarletteHTTPException` | `fail` | `HTTP_<código>` | Vacío; conserva `exc.headers` |
| `Exception` | `error` | `INTERNAL_ERROR` | Con `DEBUG`, el stack; si no, vacío |

`_translate_validation_message` traduce los tipos de error de Pydantic
(`missing`, `string_too_long`, `extra_forbidden`…) y deja el mensaje de un
`ValueError` tal como lo escribió el validador (§21).

Fuera de `DEBUG`, el handler global registra el error con el logger, lo
guarda en `ErrorLog` con una sesión propia y responde un `500` genérico. Si
guardar falla, solo se registra con `logger.exception`.

---

## 11. Integrations

Cada proveedor tiene un archivo con dos piezas:

```python
def configure_resend(settings: Settings) -> None:
    """Configura el SDK una vez; se llama desde el lifespan."""


class ResendService:
    """Operaciones del proveedor; las llama un service de dominio."""
```

Un SDK síncrono se ejecuta en un hilo para no bloquear el event loop:

```python
response = await asyncio.to_thread(
    cloudinary.uploader.upload,
    file.file,
    folder=folder,
    resource_type="image",
)
```

Ejemplo de detalle que solo conoce la integration: la URL segura que devuelve
Cloudinary es lo que se guarda en la base (`image_url`). Para eliminar la
imagen hace falta su `public_id`, que se extrae de la URL con
`CloudinaryService._extract_public_id`. Ningún service ni route interpreta esa
URL.

Las restricciones técnicas del proveedor (tipo de imagen, bloqueo de SVG,
tamaño máximo de 5 MB) viven en la integration. Las reglas del negocio, como
cuántas imágenes puede tener un producto, viven en el service.

Las integraciones de la plantilla son opcionales:

| Sin sus variables | Comportamiento |
|---|---|
| Al arrancar | `configure_<proveedor>` registra un aviso y no falla |
| Al usarla | La operación lanza `RuntimeError` con las variables que faltan; el handler global responde `500` y lo guarda en `ErrorLog` |

Así un backend que no sube imágenes ni envía correos no necesita credenciales
falsas para arrancar.

---

## 12. API y main

`app/api.py`:

```python
from fastapi import APIRouter

from app.core.system_router import router as system_router
from app.domains.pedidos.routes import router as pedidos_router

no_system_router = APIRouter(prefix="/api/v1")
no_system_router.include_router(pedidos_router)

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(no_system_router)
```

`app/main.py`:

```python
settings = get_settings()
setup_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_cloudinary(settings)
    configure_resend(settings)
    database_engine = None
    try:
        database_engine, session_factory = initialize_database(settings)
        await check_database_connection(database_engine)
        app.state.db_engine = database_engine
        app.state.db_session_factory = session_factory
        yield
    finally:
        if database_engine is not None:
            await close_database(database_engine)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
)
register_all_middlewares(app, settings)
app.include_router(api_router)
setup_openapi(app)
```

Si la base no responde al arrancar, `check_database_connection` lanza la
excepción y la aplicación no arranca: es preferible a aceptar requests que
fallarán todas.

---

## 13. Docker y despliegue

### Dockerfile de referencia

```dockerfile
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias antes del código para reutilizar la caché de Docker.
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home --uid 1000 appuser

COPY alembic.ini .
COPY migrations ./migrations
COPY seeds ./seeds
COPY app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=4)"

# Migraciones antes de levantar la API. Requiere una sola réplica.
# exec: uvicorn queda como proceso principal y recibe la señal de apagado.
# --proxy-headers: IP real del cliente detrás del proxy de la plataforma.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
```

Si `alembic upgrade head` falla, el contenedor no arranca. Con varias réplicas,
cada una ejecutaría las migraciones a la vez; por eso se exige una sola, o se
mueve la migración a un paso previo al deploy (en Railway, Pre-deploy command).

### `.dockerignore`

Un patrón por línea, como lo lee Docker:

```text
.env
.env.*
.venv/
venv/
env/
.git/
.gitignore
.vscode/
.idea/
**/__pycache__/
**/*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
tests/
docs/
requirements-dev.txt
pytest.ini
Procfile
*.md
Dockerfile
.dockerignore
```

### Health check

`GET /health` consulta `app.state.db_engine` con `check_database_connection` y
responde `200` (`healthy`) o `503` (`error`), sin exponer la excepción. No usa
`ErrorResponse`: es una respuesta técnica para la plataforma.

| Plataforma | Cómo usa `/health` |
|---|---|
| Docker / Dokploy | `HEALTHCHECK` del Dockerfile; en Dokploy también puede configurarse en Swarm Settings |
| Railway | Healthcheck Path configurado en el servicio; solo lo comprueba durante el deploy |

### Variables de entorno

Formato de `.env.example`, compatible con `--env-file`:

- `NOMBRE=valor`, sin espacios alrededor del `=`.
- Sin comillas: Docker las incluye como parte del valor.
- Comentarios solo en líneas propias.

URLs de PostgreSQL:

| Caso | Valor |
|---|---|
| Formato | `postgresql+asyncpg://USUARIO:PASSWORD@HOST:PUERTO/BASE` |
| Password con caracteres reservados | Codificados: `@` → `%40`, `#` → `%23`, `%` → `%25` |
| SSL | `?ssl=require`; SQLAlchemy pasa los parámetros a `asyncpg.connect()`, que no acepta `sslmode` |
| Supabase | Session Pooler (5432), recomendado para backends persistentes. La conexión directa requiere IPv6, que Docker no tiene por defecto. El Transaction Pooler (6543) exige desactivar los prepared statements, algo que `get_connect_args()` ya hace |
| API en Docker y PostgreSQL en el host | `host.docker.internal`, no `localhost` |
| API y PostgreSQL en la misma red Docker | El nombre del servicio como host |

### Uso

```bash
docker build -t <proyecto>-api .
docker run --rm -p 8000:8000 --env-file .env <proyecto>-api
docker exec -it <contenedor> python -m seeds.<seed>
```

### Checklist de un proyecto nuevo

1. Copiar el `Dockerfile` y el `.dockerignore` de referencia.
2. Separar `requirements.txt` y `requirements-dev.txt` con versiones fijadas.
3. Comprobar que `/health` responde `503` si PostgreSQL no está disponible.
4. Usar la misma selección de base en la aplicación y en Alembic (§7, §8).
5. Crear `.env.example` con el formato de esta sección.
6. Verificar con `docker build` y `docker run --env-file .env` que
   `alembic upgrade head` termina y `/health` responde `200`.
7. En Railway, configurar `/health` como Healthcheck Path.

---

## 14. Reglas para cambios

Antes de escribir código nuevo se busca lo que ya existe:

| Necesidad | Dónde buscar primero |
|---|---|
| Validar un formato | `shared/services/validators.py` |
| Generar un slug | `shared/services/slug.py` |
| Responder un error | `AppException` + `ErrorCode` |
| Paginar | `PaginatedResponse` |
| Exponer un árbol | `TreeResponse` |
| Comprobar un permiso | `require_permission` |
| Sincronizar una lista | `shared/services/sync.py` |

Ejemplo de "la solución más simple": si un endpoint necesita un filtro nuevo, se
agrega un query parameter y una condición en el repository. No se crea un
sistema genérico de filtros para un único caso.

---

## 15. Protección de la documentación

Antes de editar `AGENTS.md` o este archivo, se formula la regla que se quiere
documentar. Si no puede escribirse como una convención reutilizable en otros
backends, no se documenta aquí.

Ejemplos que **no** modifican la documentación:

```text
crear, renombrar o eliminar un dominio
agregar o cambiar endpoints, campos, schemas o models
generar migrations
cambiar una regla de negocio local
corregir un bug o refactorizar un módulo
```

Ejemplos que **sí** la modifican:

```text
cambiar cómo se nombran los schemas
cambiar cómo se valida la entrada en todos los dominios
agregar una pieza de infraestructura compartida
```

Al cambiar una regla de `AGENTS.md`, se revisa su sección homónima aquí para que
sus ejemplos sigan cumpliéndola.

---

## 16. Cómo se usa este documento

| Necesito | Leo |
|---|---|
| Entender por qué existe una regla | La sección con el mismo número que en `AGENTS.md` |
| Un ejemplo completo de un dominio | §18 (models), §20 (schemas), §22 (services), §23 (routes) |
| Material para copiar | §8 (env.py, migrations), §13 (Dockerfile), §22 (contrato de `sync.py`) |
| Construir un backend nuevo | §17 y §25 |

---

## 17. Clasificación de models

### De `database.md` a la clasificación

`database.md` contiene el SQL de PostgreSQL. El SQL dice qué se guarda; la
clasificación decide cómo se expone. El ejemplo de este documento parte de este
SQL (resumido):

```sql
CREATE TABLE clientes        (id UUID PRIMARY KEY, nombre TEXT NOT NULL);
CREATE TABLE datos_fiscales  (id UUID PRIMARY KEY REFERENCES clientes(id), nit TEXT NOT NULL);
CREATE TABLE productos       (id UUID PRIMARY KEY, nombre TEXT NOT NULL, precio NUMERIC(12,2),
                              stock INT NOT NULL);
CREATE TABLE etiquetas       (id UUID PRIMARY KEY, nombre TEXT NOT NULL UNIQUE);
CREATE TABLE monedas         (id UUID PRIMARY KEY, codigo TEXT NOT NULL, orden INT);
CREATE TABLE categorias      (id UUID PRIMARY KEY, nombre TEXT, padre_id UUID REFERENCES categorias(id));
CREATE TABLE pedidos         (id UUID PRIMARY KEY, numero TEXT UNIQUE,
                              cliente_id UUID REFERENCES clientes(id), estado TEXT);
CREATE TABLE direcciones     (id UUID PRIMARY KEY REFERENCES pedidos(id), calle TEXT);
CREATE TABLE lineas_pedido   (id UUID PRIMARY KEY, pedido_id UUID REFERENCES pedidos(id),
                              producto_id UUID REFERENCES productos(id), cantidad INT);
CREATE TABLE pagos           (id UUID PRIMARY KEY, pedido_id UUID REFERENCES pedidos(id),
                              monto NUMERIC(12,2));
CREATE TABLE producto_etiqueta (producto_id UUID REFERENCES productos(id),
                                etiqueta_id UUID REFERENCES etiquetas(id));
CREATE TABLE movimientos     (id UUID PRIMARY KEY, producto_id UUID REFERENCES productos(id),
                              cantidad INT, costo NUMERIC(12,2), balance_after INT,
                              reverses_id UUID REFERENCES movimientos(id),
                              idempotency_key TEXT UNIQUE);
CREATE TABLE configuracion   (id UUID PRIMARY KEY, nombre_tienda TEXT);
```

Lo que el SQL no dice y el agente pregunta: si cada foreign key es de dueño o
de referencia, si cada lista es de pocos o de muchos, y quién edita cada tabla.

### Propuesta que el agente presenta para confirmar

| Tabla | Tipo | Por qué |
|---|---|---|
| `clientes` | Raíz | Vida propia, listado y detalle |
| `datos_fiscales` | Extensión 1:1 | Uno por cliente, pero lo edita contabilidad en otra pantalla |
| `productos` | Raíz | Vida propia |
| `etiquetas` | Catálogo | Los productos las eligen; el usuario puede crear nuevas |
| `monedas` | Filas fijas | Vienen sembradas; el usuario solo cambia el orden |
| `categorias` | Catálogo con jerarquía autorreferenciada | `padre_id` apunta a la misma tabla |
| `pedidos` | Raíz | Vida propia |
| `direcciones` | Extensión 1:1 embebida | Una por pedido, se edita en el mismo formulario |
| `lineas_pedido` | Hija embebida | Pocas por pedido (máximo 50), se editan con el pedido |
| `pagos` | Hija paginada | Sin límite razonable por pedido |
| `producto_etiqueta` | Puente N:M | Solo dos foreign keys de referencia; se escribe desde el producto |
| `movimientos` | Registro | Kardex: solo se insertan filas |
| `configuracion` | Singleton | Una sola fila global |

| Relación | Clasificación |
|---|---|
| `pedidos.cliente_id` | Apunto a uno |
| `lineas_pedido.pedido_id` | Contengo pocos |
| `lineas_pedido.producto_id` | Apunto a uno |
| `pagos.pedido_id` | Contengo muchos |
| `direcciones.id` → `pedidos.id` | Contengo uno (embebida) |
| `datos_fiscales.id` → `clientes.id` | Contengo uno (no embebida) |
| `producto_etiqueta` | Apunto a varios, desde el producto |
| `movimientos.reverses_id` | Referencia al asiento anulado |

Los comentarios del SQL adelantan esta propuesta:

```sql
pedido_id UUID REFERENCES pedidos(id),     -- contengo, pocos (máx. 50)
producto_id UUID REFERENCES productos(id)  -- apunto
```

---

## 18. Models

### Raíz con relaciones

```python
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Index, text
from sqlmodel import Field, Relationship

from app.core.base_model import BaseModel
from app.shared.enums import EstadoPedido

if TYPE_CHECKING:
    from app.domains.lineas_pedido.models import LineaPedido


class Pedido(BaseModel, table=True):
    __tablename__ = "pedidos"
    __table_args__ = (
        Index(
            "uq_pedidos_numero_not_deleted",
            "numero",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )

    numero: str = Field(max_length=20)
    cliente_id: UUID = Field(foreign_key="clientes.id")
    estado: EstadoPedido = Field(default=EstadoPedido.PENDIENTE)

    lineas: list["LineaPedido"] = Relationship(
        sa_relationship_kwargs={"lazy": "raise"},
    )
```

### Hija embebida

```python
class LineaPedido(BaseModel, table=True):
    __tablename__ = "lineas_pedido"

    pedido_id: UUID = Field(foreign_key="pedidos.id", index=True)
    producto_id: UUID = Field(foreign_key="productos.id")
    cantidad: int
```

### Extensión 1:1 con id compartido

```python
class Direccion(BaseModel, table=True):
    __tablename__ = "direcciones"

    id: UUID = Field(foreign_key="pedidos.id", primary_key=True)
    calle: str = Field(max_length=200)
```

El service la crea con `Direccion(id=pedido.id, ...)`. Como `id` es primary
key, la base impide una segunda dirección para el mismo pedido.

### Jerarquía autorreferenciada

```python
class Categoria(BaseModel, table=True):
    __tablename__ = "categorias"

    nombre: str = Field(max_length=80)
    padre_id: UUID | None = Field(default=None, foreign_key="categorias.id", index=True)
```

### Puente N:M

```python
class ProductoEtiqueta(BaseModel, table=True):
    __tablename__ = "producto_etiqueta"

    producto_id: UUID = Field(foreign_key="productos.id", index=True)
    etiqueta_id: UUID = Field(foreign_key="etiquetas.id", index=True)
```

### Registro (kardex)

```python
from decimal import Decimal

from sqlalchemy import Numeric


class Movimiento(BaseModel, table=True):
    __tablename__ = "movimientos"
    __table_args__ = (
        Index("uq_movimientos_reverses_id", "reverses_id", unique=True),
        Index("uq_movimientos_idempotency_key", "idempotency_key", unique=True),
    )

    producto_id: UUID = Field(foreign_key="productos.id", index=True)
    cantidad: int
    costo: Decimal = Field(sa_type=Numeric(12, 2))
    balance_after: int
    reverses_id: UUID | None = Field(default=None, foreign_key="movimientos.id")
    idempotency_key: str = Field(max_length=64)
```

Sus índices únicos no son parciales: un Registro nunca tiene filas eliminadas.

---

## 19. Soft delete y auditoría

### Repository: filtro de eliminados y alcance

```python
@dataclass(frozen=True)
class PedidoScope:
    created_by: UUID | None = None
    all: bool = False


class PedidoRepository:
    @staticmethod
    async def get(
        db_session: AsyncSession,
        pedido_id: UUID,
        *,
        scope: PedidoScope,
        include_deleted: bool = False,
        detail: bool = False,
    ) -> Pedido | None:
        query = select(Pedido).where(Pedido.id == pedido_id)
        if not include_deleted:
            query = query.where(Pedido.is_deleted.is_(False))
        query = _apply_scope(query, scope)
        if detail:
            query = query.options(
                selectinload(Pedido.lineas.and_(LineaPedido.is_deleted.is_(False))),
            )
        return (await db_session.execute(query)).scalars().first()


def _apply_scope(query, scope: PedidoScope):
    if scope.all:
        return query
    if scope.created_by is not None:
        return query.where(Pedido.created_by == scope.created_by)
    return query.where(false())  # alcance vacío
```

`GET /{id}` llama a `get` con el valor por defecto; `GET /{id}/audit` pasa
`include_deleted=True`. El alcance se aplica igual en los dos.

### Service: eliminar con dependientes

Eliminar un producto cubre los tres casos de §19:

```python
@staticmethod
async def delete(db_session: AsyncSession, producto_id: UUID, actor: CurrentUser) -> None:
    producto = await ProductoRepository.get(db_session, producto_id, scope=_scope_for(actor))
    if producto is None:
        raise AppException("Producto no encontrado.", 404, ErrorCode.RESOURCE_NOT_FOUND)

    # Referencia no eliminada: una línea de pedido lo usa → 409.
    if await LineaPedidoRepository.exists_for_producto(db_session, producto_id):
        raise AppException("El producto está en pedidos.", 409, ErrorCode.CONFLICT)

    # Registro: un movimiento del kardex cuenta como referencia → 409.
    if await MovimientoRepository.exists_for_producto(db_session, producto_id):
        raise AppException("El producto tiene movimientos.", 409, ErrorCode.CONFLICT)

    # Puente N:M: sus enlaces caen en cascada, con los mismos deleted_at y deleted_by.
    now = utc_now()
    await ProductoEtiquetaRepository.mark_deleted_by_producto(db_session, producto_id, now, actor.id)
    ProductoRepository.mark_deleted(producto, now, actor.id)
    await db_session.commit()
```

Para retirar un producto que ya se vendió, sin eliminarlo, se usa un estado
como `is_visible`.

Una cascada se marca con un `UPDATE` sobre los hijos no eliminados:

```python
@staticmethod
async def mark_deleted_by_pedido(db_session, pedido_id, now, actor_id) -> None:
    await db_session.execute(
        update(LineaPedido)
        .where(LineaPedido.pedido_id == pedido_id, LineaPedido.is_deleted.is_(False))
        .values(is_deleted=True, deleted_at=now, deleted_by=actor_id,
                updated_at=now, updated_by=actor_id)
    )
```

Las comprobaciones de integridad (las referencias que bloquean, los hijos en
cascada) consultan todas las filas no eliminadas, sin alcance (§24).

### Anular un asiento de un Registro

```python
@staticmethod
async def anular(db_session: AsyncSession, movimiento_id: UUID, actor: CurrentUser) -> Movimiento:
    original = await MovimientoRepository.get(db_session, movimiento_id, scope=_scope_for(actor))
    if original is None:
        raise AppException("Movimiento no encontrado.", 404, ErrorCode.RESOURCE_NOT_FOUND)

    # Bloquea la fila cuyo saldo se mueve hasta el commit.
    producto = await ProductoRepository.get_for_update(db_session, original.producto_id)
    reverso = Movimiento(
        producto_id=original.producto_id,
        cantidad=-original.cantidad,
        costo=original.costo,
        balance_after=producto.stock - original.cantidad,
        reverses_id=original.id,
        idempotency_key=f"reverso:{original.id}",
        created_by=actor.id,
    )
    producto.stock = reverso.balance_after
    db_session.add(reverso)
    await db_session.commit()
    return reverso
```

`get_for_update` usa `select(Producto).where(...).with_for_update()`. El índice
único sobre `reverses_id` rechaza un segundo reverso del mismo asiento aunque
dos peticiones lleguen a la vez.

---

## 20. Schemas

### Archivo completo de un dominio

```python
from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.domains.clientes.schemas import ClienteRef, ClienteResponse
from app.domains.direcciones.schemas import DireccionCreate, DireccionResponse, DireccionUpdate
from app.domains.lineas_pedido.schemas import LineaCreate, LineaNestedItem, LineaResponseDetail
from app.shared.enums import EstadoPedido
from app.shared.schemas.base import AuditMixin, SchemaBase
from app.shared.services.validators import validator_non_empty_text


# Entrada plana
class PedidoCreate(SchemaBase):
    numero: str = Field(max_length=20)
    cliente_id: UUID

    @field_validator("numero", mode="before")
    @classmethod
    def validate_numero(cls, value: object) -> str:
        return validator_non_empty_text(value)


# Entrada con relaciones: hereda la plana
class PedidoCreateNested(PedidoCreate):
    direccion: DireccionCreate
    lineas: list[LineaCreate] = Field(min_length=1, max_length=50)


class PedidoUpdate(SchemaBase):
    numero: str = Field(default=None, max_length=20)

    @field_validator("numero", mode="before")
    @classmethod
    def validate_numero(cls, value: object) -> str:
        if value is None:
            raise ValueError("El número no puede ser null.")
        return validator_non_empty_text(value)


class PedidoUpdateNested(PedidoUpdate):
    direccion: DireccionUpdate | None = None
    lineas: list[LineaNestedItem] | None = Field(default=None, max_length=50)


# Salida plana
class PedidoResponse(SchemaBase):
    id: UUID
    numero: str
    cliente_id: UUID
    estado: EstadoPedido
    created_at: datetime
    updated_at: datetime


class PedidoResponseAudit(AuditMixin, PedidoResponse):
    pass


class PedidoRef(SchemaBase):
    id: UUID
    numero: str


# Salidas con relaciones: heredan la plana
class PedidoResponseItemList(PedidoResponse):
    cliente: ClienteRef
    lineas_count: int


class PedidoResponseDetail(PedidoResponse):
    cliente: ClienteResponse
    direccion: DireccionResponse
    lineas: list[LineaResponseDetail]
```

Qué muestra el ejemplo:

- `PedidoCreate` no tiene `id`, `estado` ni auditoría: los asigna el service.
- `PedidoUpdate` no tiene `cliente_id`: una referencia de dueño no cambia, y
  `estado` cambia solo con endpoints de acción.
- `PedidoResponseItemList` lleva un resumen (`lineas_count`), nunca la lista.
- `LineaResponseDetail` es el `ResponseDetail` de la línea: incluye su
  `producto: ProductoResponse`, una referencia a un paso, con schema plano.
- La auditoría queda al final de `PedidoResponseAudit` porque `AuditMixin` va
  primero en la herencia.

### La hija embebida

```python
class LineaCreate(SchemaBase):
    producto_id: UUID
    cantidad: int = Field(ge=1, le=999)

    @field_validator("cantidad", mode="before")
    @classmethod
    def validate_cantidad(cls, value: object) -> int:
        return validator_integer(value)


class LineaNestedItem(LineaCreate):
    id: UUID | None = None
```

`LineaCreate` no tiene `pedido_id`: lo asigna el service del pedido.

### Ejemplo de documentación

```python
model_config = ConfigDict(
    json_schema_extra={
        "example": {
            "numero": "P-000123",
            "cliente_id": "8f14e45f-ceea-467a-9575-6b3f0c1a2b3c",
        }
    }
)
```

Pydantic ordena alfabéticamente las claves de un ejemplo y FastAPI quita sus
`null`. `core/openapi.py` reemplaza cada ejemplo del OpenAPI por el original
del schema, con su orden; si dos schemas comparten nombre con ejemplos
distintos, no reemplaza ninguno.

### Jerarquías

`GET /categorias/arbol` devuelve `TreeResponse[CategoriaResponse]`: cada nodo es
`{"data": {...}, "children": [...]}`. El `ResponseDetail` de una categoría solo
embebe sus hijos directos.

---

## 21. Validaciones

### Qué valida cada capa, con un email

```text
Schema      → validator_email: tipo, formato y normalización
Service     → consulta si existe otro usuario no eliminado con ese email → 409
Repository  → ejecuta esa consulta, sin alcance
Model       → índice único parcial sobre email, para condiciones de carrera
```

### Validadores disponibles

```text
Texto       validator_text, validator_non_empty_text, validator_name,
            validator_slug_source, validator_slug
Contacto    validator_email, validator_phone, validator_http_url
Seguridad   validator_password
Números     validator_integer, validator_non_negative_integer, validator_positive_integer,
            validator_non_negative_money, validator_positive_money, validator_percentage
Fechas      validator_date, validator_datetime, validator_time
Ubicación   validator_latitude, validator_longitude
Otros       validator_boolean, validator_hex_color, validator_json_object
```

Un validador nuevo entra en la librería solo si sirve a más de un dominio; uno
propio de un dominio vive en su `schemas.py`.

### Plantilla de un validador nuevo

```python
def validator_sku(value: object) -> str:
    """Normaliza un SKU: mayúsculas, sin espacios, 4 a 20 caracteres."""
    if not isinstance(value, str):
        raise ValueError("El SKU debe ser texto.")
    normalized = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9-]{4,20}", normalized):
        raise ValueError("El SKU solo admite letras, números y guiones (4 a 20).")
    return normalized
```

- Comprueba el tipo antes de usar métodos de `str`.
- El mensaje es para el cliente y en español: el handler de §10 lo expone tal
  cual.
- Un límite que depende de la columna (`max_length=20`) iría en `Field`; aquí
  el largo es parte del formato del SKU y vale en cualquier schema.

---

## 22. Services

### Crear con relaciones

```python
class PedidoService:
    @staticmethod
    async def create(
        db_session: AsyncSession,
        data: PedidoCreateNested,
        actor: CurrentUser,
    ) -> PedidoResponseDetail:
        # Referencias recibidas: existen, no están eliminadas y están en el alcance.
        await ClienteService.ensure_reference(db_session, data.cliente_id, actor)
        await ProductoService.ensure_references(db_session, [l.producto_id for l in data.lineas], actor)
        await PedidoService._ensure_numero_unique(db_session, data.numero)

        pedido = Pedido(**data.model_dump(include={"numero", "cliente_id"}), created_by=actor.id)
        db_session.add(pedido)
        await db_session.flush()  # asigna pedido.id antes de crear los hijos

        db_session.add(Direccion(id=pedido.id, **data.direccion.model_dump(), created_by=actor.id))
        for linea in data.lineas:
            db_session.add(LineaPedido(pedido_id=pedido.id, **linea.model_dump(), created_by=actor.id))

        await db_session.commit()
        return await PedidoService.get(db_session, pedido.id, actor)  # recarga con su árbol
```

`ensure_reference` responde `422` si el id no existe, está eliminado o está
fuera del alcance del actor.

### Editar con sincronización

```python
@staticmethod
async def update(db_session, pedido_id, data: PedidoUpdateNested, actor) -> PedidoResponseDetail:
    pedido = await PedidoRepository.get(db_session, pedido_id, scope=_scope_for(actor), detail=True)
    if pedido is None:
        raise AppException("Pedido no encontrado.", 404, ErrorCode.RESOURCE_NOT_FOUND)

    changes = data.model_dump(exclude_unset=True, exclude={"direccion", "lineas"})
    for field, value in changes.items():
        setattr(pedido, field, value)

    if data.lineas is not None:
        plan = plan_sync({linea.id for linea in pedido.lineas}, data.lineas)
        # 1. eliminar y flush, 2. actualizar, 3. crear
        ...
        await db_session.flush()
        ...

    pedido.updated_at = utc_now()
    pedido.updated_by = actor.id
    await db_session.commit()
    return await PedidoService.get(db_session, pedido.id, actor)
```

### `shared/services/sync.py`

```python
plan = plan_sync(existing_ids={linea.id for linea in pedido.lineas}, items=data.lineas)
plan.to_delete   # frozenset[UUID]: existentes que no vinieron en la lista
plan.to_update   # tuple: elementos con id
plan.to_create   # tuple: elementos sin id

plan = plan_ids_sync(existing_ids=etiquetas_actuales, received_ids=data.etiqueta_ids)
plan.to_delete   # enlaces que se eliminan
plan.to_create   # enlaces nuevos; los que se conservan no aparecen
```

`plan_sync` lanza `ForeignChildError` (un `ValueError` con sus `ids`) si un
elemento trae un id que no pertenece al padre o está eliminado; el service la
convierte en un `422`:

```python
try:
    plan = plan_sync(existing_ids, data.lineas)
except ForeignChildError as error:
    raise AppException(
        "Hay líneas que no pertenecen a este pedido.",
        422,
        ErrorCode.VALIDATION_ERROR,
        details={"lineas": sorted(map(str, error.ids))},
    ) from error
```

Por qué una función pura:

- se prueba sin base de datos;
- todos los services sincronizan igual;
- el service conserva el control de la transacción y del orden de operaciones.

### Por qué `flush()` antes de actualizar y crear

Un índice único parcial solo considera filas no eliminadas. Si el cliente
elimina la línea con el código `A` y crea otra con el mismo código en la misma
petición, PostgreSQL debe ver la eliminación antes que la creación. El
`flush()` la envía dentro de la transacción, sin confirmarla.

---

## 23. Routes

### Archivo completo de un dominio

```python
router = APIRouter(prefix="/pedidos", tags=["Pedidos"])


@router.get(
    "/",
    response_model=PaginatedResponse[PedidoResponseItemList],
    summary="Listar pedidos",
    responses=error_responses(401, 403, 422, 500),
)
async def list_pedidos(
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PEDIDO, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    cliente_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedResponse[PedidoResponseItemList]:
    return await PedidoService.list(
        db_session, actor=current_user, page=page, per_page=per_page, cliente_id=cliente_id,
    )


@router.get(
    "/{pedido_id}",
    response_model=PedidoResponseDetail,
    summary="Obtener un pedido",
    responses=error_responses(401, 403, 404, 500),
)
async def get_pedido(
    pedido_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PEDIDO, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoResponseDetail:
    return await PedidoService.get(db_session, pedido_id, current_user)


@router.get(
    "/{pedido_id}/audit",
    response_model=PedidoResponseAudit,
    summary="Auditar un pedido",
    responses=error_responses(401, 403, 404, 500),
)
async def audit_pedido(
    pedido_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PEDIDO, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoResponseAudit:
    return await PedidoService.get(db_session, pedido_id, current_user, include_deleted=True)


@router.post(
    "/",
    response_model=PedidoResponseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un pedido",
    responses=error_responses(401, 403, 409, 422, 500),
)
async def create_pedido(
    data: PedidoCreateNested,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PEDIDO, Action.CREATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoResponseDetail:
    return await PedidoService.create(db_session, data, current_user)


@router.patch(
    "/{pedido_id}",
    response_model=PedidoResponseDetail,
    summary="Editar un pedido",
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
async def update_pedido(
    pedido_id: UUID,
    data: PedidoUpdateNested,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PEDIDO, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoResponseDetail:
    return await PedidoService.update(db_session, pedido_id, data, current_user)


@router.delete(
    "/{pedido_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un pedido",
    responses=error_responses(401, 403, 404, 409, 500),
)
async def delete_pedido(
    pedido_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PEDIDO, Action.DELETE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await PedidoService.delete(db_session, pedido_id, current_user)


@router.post(
    "/{pedido_id}/confirmar",
    response_model=PedidoResponseDetail,
    summary="Confirmar un pedido",
    responses=error_responses(401, 403, 404, 409, 500),
)
async def confirmar_pedido(
    pedido_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.PEDIDO, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> PedidoResponseDetail:
    return await PedidoService.confirmar(db_session, pedido_id, current_user)
```

Cada route solo traduce HTTP: recibe, autoriza con su dependencia y delega.

### La hija embebida solo expone su auditoría

```python
router = APIRouter(prefix="/lineas-pedido", tags=["Líneas de pedido"])


@router.get(
    "/{linea_id}/audit",
    response_model=LineaResponseAudit,
    summary="Auditar una línea de pedido",
    responses=error_responses(401, 403, 404, 500),
)
async def audit_linea(
    linea_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.LINEA_PEDIDO, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> LineaResponseAudit:
    return await LineaPedidoService.audit(db_session, linea_id, current_user)
```

El service busca la línea con el alcance de su pedido (§24).

---

## 24. Security

### Primitivas de `core/security.py`

| Función | Qué hace |
|---|---|
| `hash_password`, `verify_password` | Argon2 con `PasswordHash.recommended()`; un hash desconocido verifica como `False` |
| `DUMMY_PASSWORD_HASH` | Hash que se verifica cuando el usuario no existe, para que el login tarde lo mismo y no revele qué emails existen |
| `create_access_token`, `decode_access_token` | JWT HS256 con `iat`, `exp` y `jti`; el token inválido decodifica como `None` |
| `create_refresh_token`, `hash_refresh_token` | Token aleatorio de 64 bytes; en la base solo se guarda su SHA-256 |
| `create_csrf_token`, `verify_csrf_token` | HMAC del refresh token con `CSRF_SECRET_KEY`, comparado en tiempo constante |
| `create_one_time_token`, `hash_one_time_token` | Tokens de un solo uso, como el de recuperación de contraseña |

### Flujo de autenticación

Es el flujo que implementa `auth/` al construirse. Sus models (`AuthSession`,
`PasswordResetToken`) y las primitivas de `core/security.py` ya lo soportan.

```text
login     → access token (JWT, corto)  + refresh token (cookie HttpOnly) + CSRF token (body)
request   → Authorization: Bearer <access token>
refresh   → cookie + X-CSRF-Token → rota la sesión: la anterior queda revocada con replaced_by
logout    → revoca la sesión
reset     → token de un solo uso, guardado como hash, con vencimiento
```

- **Por qué dos claves.** Con una sola, quien obtuviera `SECRET_KEY` podría
  fabricar también tokens CSRF.
- **Por qué rotar.** `AuthSession.family_id` agrupa las sesiones que nacen de
  un mismo login. Si llega un refresh token ya reemplazado, alguien lo copió, y
  se puede revocar la familia completa.
- **Por qué hash.** Si la base se filtra, los refresh tokens y los tokens de
  recuperación guardados no sirven para iniciar sesión.

### Leer la matriz de permisos

Ejemplo de un proyecto con ventas; la plantilla solo trae `Module.USUARIO`:

```python
ROLE_PERMISSIONS: dict[Role, dict[Module, frozenset[Action]]] = {
    Role.ADMIN: {
        Module.VENTA: frozenset({Action.CREATE, Action.READ, Action.UPDATE}),  # sin DELETE: no anula ventas confirmadas
        Module.VENTA_PAGO: frozenset({Action.UPDATE}),  # los pagos se registran con su venta; UPDATE solo sube el comprobante
        Module.FINANZAS: frozenset({Action.READ}),  # reportes de solo lectura
    },
}
```

- La fila de un rol se lee como una tabla: todos los módulos, uno por línea.
- Un comentario explica cada entrada con menos acciones que el resto.
- `VENTA_PAGO` muestra la regla de las hijas: su módulo solo lista la acción
  de su propia ruta; registrarlos lo autoriza el permiso de la venta.

### Alcance completo de un módulo

```python
# permissions.py
PEDIDO_GLOBAL_SCOPE_ROLES: frozenset[Role] = frozenset({Role.SUPERADMIN, Role.OWNER, Role.ADMIN})
PEDIDO_OWN_SCOPE_ROLES: frozenset[Role] = frozenset({Role.CAJERO})


# pedidos/services.py
def _scope_for(actor: CurrentUser) -> PedidoScope:
    if actor.role in PEDIDO_GLOBAL_SCOPE_ROLES:
        return PedidoScope(all=True)
    if actor.role in PEDIDO_OWN_SCOPE_ROLES:
        return PedidoScope(created_by=actor.id)
    return PedidoScope()
```

El mismo `_scope_for` lo usan `get`, `list`, `audit`, `update`, `delete`,
`confirmar` y el `audit` de las líneas. Con un rol nuevo sin grupo, el alcance
vacío no devuelve nada hasta que alguien decida su grupo.

### `404` fuera de alcance, `403` sin la acción

```text
Cajero A pide GET /pedidos/{id} de un pedido del cajero B → 404 (no sabe que existe)
OWNER pide PATCH /usuarios/{id} de un SUPERADMIN           → 403 (lo ve, no puede modificarlo)
```

---

## 25. Orden de construcción de un backend nuevo

### Etapa horizontal con el ejemplo

| Paso | Resultado |
|---|---|
| 1. Leer `database.md` | El SQL de §17 |
| 2. Clasificar | Las tablas de §17, confirmadas con el usuario |
| 3. Permisos | `Module.PEDIDO`, `Module.LINEA_PEDIDO`, …; la matriz; `PEDIDO_*_SCOPE_ROLES` |
| 4. Models y migración | Los models de §18 con sus `Relationship()`; una migración con el trigger de `movimientos` y las `monedas` |
| 5. Validadores | Los que falten, como `validator_sku` (§21) |
| 6. Schemas | Ronda 1: `PedidoCreate`, `PedidoResponse`, … Ronda 2: `PedidoCreateNested`, `PedidoResponseDetail`, … (§20) |

### Etapa vertical con el ejemplo

```text
1. Sin foreign keys, completos    → monedas, etiquetas, configuracion
2. Primera vuelta, padres → hijos → clientes, productos, pedidos
                                    (datos_fiscales, direcciones, lineas_pedido y
                                    producto_etiqueta: solo repository)
3. Segunda vuelta, hijos → padres → lineas_pedido, direcciones, datos_fiscales,
                                    productos, clientes, pedidos
```

`categorias` (jerarquía), `pagos` y `movimientos` no tienen hijos en otros
dominios: completan las dos vueltas a la vez en cuanto existen los dominios a
los que apuntan.

En la primera vuelta, `POST /pedidos` recibe `PedidoCreate` y responde
`PedidoResponse`. En la segunda pasa a `PedidoCreateNested` →
`PedidoResponseDetail`. El frontend que ya usaba la primera versión sigue
funcionando: las versiones con relaciones heredan de las planas y solo agregan
campos.

### Checklist de un dominio

```text
[ ] Tipo y relaciones confirmados (§17)
[ ] Module y entradas en la matriz; grupo de alcance si lo necesita (§24)
[ ] Model con índices parciales y Relationship() (§18)
[ ] Migration revisada a mano (§8)
[ ] Schemas de su fila en la tabla de tipos, con ejemplos (§20)
[ ] Repository con soft delete, alcance y carga de relaciones (§22)
[ ] Service con referencias validadas, auditoría y transacción (§22)
[ ] Routes de sus celdas "ruta" y su /audit, con error_responses (§23)
[ ] Router registrado en no_system_router (§12)
[ ] Tests: permisos (403), alcance por rol (404), validación (422), conflicto (409)
```

### Cambios después de la construcción inicial

Agregar un campo a `pedidos`:

```text
model → migration (revisada) → schemas que lo exponen o lo reciben
      → validador si es de entrada → repository si se filtra por él → tests
```

No se repite el orden completo: solo se tocan las capas afectadas.
