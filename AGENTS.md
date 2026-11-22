# AGENTS.md

Este archivo contiene las reglas que deben aplicarse siempre al trabajar en este backend.

Para detalles de arquitectura, responsabilidades por archivo, ejemplos y decisiones técnicas ampliadas, consultar `ARCHITECTURE.md` solo cuando la tarea lo requiera.

---

## 1. Stack

- Python 3.14
- FastAPI, servido con uvicorn
- PostgreSQL
- SQLModel para modelos persistentes
- SQLAlchemy async / `AsyncSession`
- asyncpg
- Pydantic para schemas
- pydantic-settings para la configuración
- Alembic para migraciones
- python-jose para JWT
- pwdlib[argon2] para hash de contraseñas
- httpx como cliente HTTP async
- pytest + pytest-asyncio para tests

No añadir dependencias que no estén en esta lista o en `requirements.txt` sin
aprobación. Una dependencia aprobada se agrega a `requirements.txt` (o a
`requirements-dev.txt` si solo es de desarrollo) con versión fijada `==`.

Regla fundamental:

```text
models.py  → SQLModel
schemas.py → Pydantic
```

Models y schemas son capas independientes.

Nunca hacer herencia entre un modelo persistente y un schema.

La duplicación razonable de campos entre ambas capas es aceptada para mantener desacopladas la persistencia y la API.

---

## 2. Estructura de `app/`

`app/` contiene únicamente estas cinco carpetas principales:

```text
app/
├── core/
├── domains/
├── integrations/
├── middlewares/
└── shared/
```

Además:

```text
app/
├── __init__.py
├── api.py
└── main.py
```

No crear nuevas carpetas raíz dentro de `app/` sin una necesidad arquitectónica explícita.

---

## 3. Responsabilidades principales

### `core/`
Infraestructura fundamental.

Contiene:

```text
base_model.py
config.py
database.py
logging.py
openapi.py
security.py
system_router.py
```

No colocar lógica funcional de dominios dentro de `core/`.

### `domains/`
Funcionalidad de negocio.

Estructura estándar:

```text
<domain>/
├── __init__.py
├── models.py
├── schemas.py
├── repositories.py
├── services.py
└── routes.py
```

`auth/` incluye además `dependencies.py`.

`error_logs/` es obligatorio y contiene como mínimo su modelo y el repository
que encapsula su persistencia.

### `integrations/`
Adaptadores de proveedores externos, por ejemplo `cloudinary.py`, `resend.py`
o `redis.py`.

### `middlewares/`
Comportamiento HTTP global.

```text
cors.py
exception_handlers.py
limiter.py
```

### `shared/`
Código realmente reutilizable entre dominios.

No utilizarlo como carpeta miscelánea.

---

## 4. Imports entre capas

Mantener:

```text
routes
↓
services
↓
repositories
↓
models
```

Para proveedores:

```text
services
↓
integrations
```

Evitar:

```text
models → services
models → routes
repositories → services
repositories → routes
services → routes
schemas → routes
integrations → routes
routes → repositories
```

---

## 5. Imports y archivos `__init__.py`

- Los archivos `__init__.py` están vacíos por defecto y nunca funcionan como
  fachada: sin reexportaciones ni `__all__`.
- Cada símbolo se importa desde el archivo donde está definido.
- Los imports propios son absolutos desde `app.`; nunca relativos.
- Orden: librería estándar, terceros y propios, en tres grupos separados por
  una línea en blanco y en orden alfabético dentro de cada grupo.

Usar:

```python
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import select

from app.core.database import get_db
from app.domains.users.models import User
from app.domains.users.schemas import UserResponse
```

No usar:

```python
from app.domains.users import User, UserResponse  # fachada desde __init__.py
from .models import User                          # import relativo
```

---

## 6. Config

Toda configuración proviene de `Settings` en `core/config.py`. Fuera de ese
archivo no se lee `.env` ni se instancia `Settings()`: el único acceso es
`get_settings()`, cacheado con `lru_cache`.

- `main.py` lo llama una vez.
- Routes y dependencias usan `Depends(get_settings)`.
- El resto de módulos recibe `settings: Settings` como parámetro.

`ENVIRONMENT` es la fuente principal de comportamiento:

```text
development
staging
production
test
```

Propiedades como `DEBUG`, expiraciones, cookies y CORS pueden derivarse de `ENVIRONMENT`.

---

## 7. Base de datos

`core/database.py` administra:

```text
AsyncEngine
async_sessionmaker
initialize_database
check_database_connection
get_db
close_database
```

Nombres oficiales en `app.state`:

```text
app.state.db_engine
app.state.db_session_factory
```

No utilizar nombres alternativos para estos objetos.

En routes y dependencias la sesión se obtiene con `Depends(get_db)`: una sesión
por request, compartida por todas las dependencias que la piden.

Fuera del flujo de `Depends()` (exception handler, background tasks, scripts)
se abre una sesión propia desde `app.state.db_session_factory`; nunca se
reutiliza la sesión de la request. Una background task recibe ids, no models
ni la sesión, y recarga los datos con su propia sesión.

Una `AsyncSession` no se comparte entre tareas concurrentes: no usar
`asyncio.gather` con la misma sesión.

El proyecto utiliza exactamente dos bases de datos, seleccionadas únicamente
mediante `ENVIRONMENT`:

```text
production                    → DATABASE_URL
development | test | staging → TEST_DATABASE_URL
```

`DATABASE_URL` está reservada para los datos reales de producción.
`TEST_DATABASE_URL` es la base no productiva compartida por desarrollo,
pruebas y staging. Mientras estos entornos compartan la misma base, las pruebas
automatizadas no deben vaciar tablas ni destruir datos sin una protección
explícita.

La selección de la base no depende de `DEBUG`. Tanto la aplicación en
`core/database.py` como Alembic en `migrations/env.py` deben aplicar exactamente
la misma regla.

---

## 8. Alembic

Las tablas solo se crean o modifican con migrations de Alembic; nunca en
startup ni con `SQLModel.metadata.create_all()`.

Configuración (`alembic init -t async migrations`):

- `env.py` se conecta igual que `core/database.py` (§7), importa todos los
  `models.py` y define `target_metadata = SQLModel.metadata`.
- `SQLModel.metadata` define `naming_convention`, para que todo constraint e
  índice tenga un nombre predecible.
- `script.py.mako` incluye `import sqlmodel`.

Flujo:

```bash
alembic revision --autogenerate -m "descripcion"
alembic upgrade head
```

La migration autogenerada es un borrador y siempre se revisa antes de aplicarla.
Autogenerate no detecta renombres (los genera como eliminar + crear y se pierden
datos), triggers, cambios de Enum ni de `server_default`; eso se escribe a mano.

Una migration ya aplicada no se edita: el cambio va en una migration nueva.

---

## 9. Logging

Todos los módulos utilizan:

```python
from app.core.logging import get_logger

logger = get_logger(__name__)
```

No configurar logging localmente.

`setup_logging(settings)` se ejecuta una sola vez durante el arranque.

---

## 10. Middlewares

`middlewares/__init__.py` es el punto único de registro:

```python
register_exception_handlers(app, settings)
register_rate_limiter(app)
register_cors(app, settings)
```

### CORS
Solo configura `CORSMiddleware`.

### Limiter
Solo configura SlowAPI y guarda:

```text
app.state.limiter
```

El handler `429` vive únicamente en `exception_handlers.py`.

`memory://` es válido para una sola instancia/proceso efectivo. Si existen varios workers o instancias, usar almacenamiento compartido como Redis.

### Exception handlers

Centraliza:

```text
AppException
RequestValidationError
RateLimitExceeded
StarletteHTTPException
Exception
```

Los errores inesperados:

```text
→ se registran con logging
→ pueden persistirse en ErrorLog
→ no exponen detalles internos fuera de DEBUG
```

El handler global puede utilizar `app.state.db_session_factory` porque no usa
el flujo normal de `Depends(get_db)`, pero delega las queries y la persistencia
de `ErrorLog` en su repository.

---

## 11. Integrations

Las integrations encapsulan SDKs y proveedores externos. Solo aplican
restricciones técnicas para proteger o usar al proveedor; nunca deciden reglas
funcionales del dominio.

Los detalles propios del proveedor (formatos de URL, identificadores, parseo de
respuestas) se resuelven solo dentro de su integration; no se duplican en
routes ni services.

Si el SDK es síncrono, sus llamadas se ejecutan con `asyncio.to_thread()` para
no bloquear el event loop.

---

## 12. API y main

`api.py` y `main.py` son archivos de composición y se mantienen limpios: solo
importan y conectan piezas definidas en otros módulos. No definen endpoints,
schemas, helpers, configuración ni lógica. Si algo requiere más que una
llamada, se implementa en su módulo (`core/`, `middlewares/`, `integrations/`
o el dominio) y aquí solo se invoca.

`api.py` solo contiene `include_router`:

```text
api_router
├── system_router      → core/system_router.py: / y /health
└── no_system_router   → prefijo /api/v1; un include_router por dominio
```

`main.py`:

- Al importarse: obtiene settings, configura logging, crea FastAPI, registra
  middlewares, incluye `api_router` y llama a `setup_openapi`.
- En el lifespan: configura integrations, inicializa y comprueba PostgreSQL,
  guarda `db_engine` y `db_session_factory` en `app.state` y cierra los
  recursos al apagar.

---

## 13. Docker y despliegue

Una única imagen Docker sirve para todos los entornos y plataformas (Dokploy
con Traefik, Railway); el comportamiento cambia solo por variables de entorno.
No crear Dockerfiles por entorno ni usar `docker-compose` en producción:
PostgreSQL es externo al contenedor.

Archivos:

```text
Dockerfile
.dockerignore         → excluye .env*, .venv, .git, tests y cachés
.env.example          → todas las variables, sin valores reales
requirements.txt      → solo producción, versiones fijadas con ==
requirements-dev.txt  → -r requirements.txt + herramientas de desarrollo
```

### Imagen

- Base `python:<versión>-slim`, con la versión de §1.
- Copiar e instalar `requirements.txt` antes que el código, para reutilizar la
  caché de capas.
- Copiar carpetas explícitas (`app`, `migrations`, `seeds`, `alembic.ini`);
  nunca `COPY . .`.
- Ejecutar como usuario sin privilegios.
- Los secretos nunca entran en la imagen; se configuran como variables de
  entorno en la plataforma.

### Arranque

- `CMD` en exec form: `["sh", "-c", "alembic upgrade head && exec uvicorn ..."]`.
  `exec` deja a uvicorn como proceso principal, para que reciba la señal de
  apagado y el lifespan cierre los recursos.
- uvicorn escucha en `0.0.0.0:${PORT:-8000}`; Railway inyecta `PORT`.
- `--proxy-headers --forwarded-allow-ips='*'`, válido solo porque la aplicación
  nunca se expone sin el proxy de la plataforma.
- Un proceso por contenedor: sin `--workers` ni `--reload`; se escala con
  réplicas.
- `alembic upgrade head` en el `CMD` exige una sola réplica. Con varias, la
  migración pasa a un paso previo al deploy (en Railway, Pre-deploy command).
- Los seeds se incluyen en la imagen pero nunca se ejecutan al arrancar.

### Health check

`/health` vive en `core/system_router.py`, fuera de `/api/v1` y sin
autenticación. Comprueba PostgreSQL y responde `200` o `503`.

- El Dockerfile define `HEALTHCHECK` contra `/health` con `urllib`, sin
  instalar `curl`.
- En Railway se configura además `/health` como Healthcheck Path del servicio;
  Railway solo lo comprueba durante el deploy.

### Variables y PostgreSQL

- `.env.example` usa el formato de `--env-file`: `NOMBRE=valor`, sin espacios ni
  comillas y sin comentarios al final de la línea. `Settings` trata una
  variable vacía como no definida.
- URL: `postgresql+asyncpg://USUARIO:PASSWORD@HOST:PUERTO/BASE`, con los
  caracteres reservados del password codificados.
- SSL con `?ssl=require`; asyncpg no acepta `sslmode`.
- En Supabase, Session Pooler (5432), recomendado para backends persistentes.
  La conexión directa requiere IPv6.

Dockerfile de referencia, `.dockerignore` completo, hosts según la red y
checklist: `ARCHITECTURE.md` §13.

---

## 14. Reglas para cambios

Antes de modificar código:

1. Revisar el código relacionado.
2. Reutilizar funciones, services y handlers existentes; no duplicarlos.
3. No crear archivos o capas innecesarias.
4. Elegir la solución más simple compatible con las reglas de este documento.

---

## 15. Protección de la documentación

`AGENTS.md` y `ARCHITECTURE.md` describen convenciones estables y reutilizables
de la plantilla, no el detalle de cada módulo o tarea. No se modifican como
efecto secundario de un cambio funcional: crear o cambiar un dominio,
endpoint, campo, schema, service, validación, regla de negocio o migration, o
hacer una corrección o refactor local, no justifica tocarlos.

Solo se modifican cuando la decisión:

- cambia una regla arquitectónica transversal;
- será aplicable a los módulos futuros;
- resulta estable y útil para reutilizar la plantilla en otros servicios; o
- ha sido solicitada explícitamente como un cambio de documentación.

Lo específico de la aplicación o de un dominio queda en el código, los tests,
las migrations o la documentación de ese dominio.

---

## 16. Cuándo consultar `ARCHITECTURE.md`

`ARCHITECTURE.md` usa la misma numeración que este archivo: su §N amplía el §N
de aquí con el porqué de la regla, ejemplos completos y material de referencia.
No se lee completo ni antes de cada cambio: solo la sección con el número de la
regla que se necesita ampliar.

Conviene consultarlo sobre todo para:

| Necesidad | Sección de `ARCHITECTURE.md` |
|---|---|
| Configurar Alembic o escribir una migration a mano | §8 |
| Copiar el Dockerfile, el `.dockerignore` o el checklist de despliegue | §13 |
| Ver la clasificación de un sistema completo a partir de su SQL | §17 |
| Ver models, schemas, services y routes completos de un dominio | §18, §20, §22, §23 |
| El contrato de `shared/services/sync.py` | §22 |

`ARCHITECTURE.md` no define reglas nuevas. Si contradice este archivo,
prevalece `AGENTS.md`.

---

## 17. Clasificación de models

Antes de escribir un model se clasifica: su tipo y cada una de sus relaciones.
Models, soft delete, schemas y routes se derivan de esta clasificación.

### Tipos

El tipo define qué operaciones admite el model y dónde ocurre cada una:

```text
ruta    → endpoint propio del model
padre   → a través del POST / PATCH / GET del padre
interno → solo lo ejecuta el service, sin endpoint
—       → la operación no existe
```

| Tipo | Qué es | Crear | Editar | Listar | Leer uno | Eliminar |
|---|---|---|---|---|---|---|
| Raíz | Entidad central con vida propia | ruta | ruta | ruta | ruta | ruta |
| Hija paginada | "Contengo muchos": listado propio, filtrado por el padre | ruta | ruta | ruta | ruta | ruta |
| Hija embebida | "Contengo pocos" | padre | padre | — | padre | padre |
| Catálogo | Valores que otras tablas eligen en un select | ruta | ruta | ruta | ruta | ruta |
| Singleton | Una sola fila, global o por dueño | — | ruta | — | ruta | — |
| Extensión 1:1 | "Contengo uno" que se edita aparte del padre: otra pantalla, otro permiso o datos sensibles. Ej.: datos fiscales de un cliente | padre | ruta | — | ruta | — |
| Extensión 1:1 embebida | "Contengo uno" que se edita junto con el padre, en el mismo formulario y con el mismo permiso. Ej.: dirección de envío de un pedido | padre | padre | — | padre | — |
| Filas fijas | Filas sembradas en una migration con claves fijas; el usuario solo ajusta título, visibilidad u orden | — | ruta | ruta | ruta | — |
| Registro | Solo se insertan filas, como un kardex (§19); las inserta el service desde un endpoint de acción | interno | — | ruta | ruta | — |
| Puente N:M | Tabla de enlace con solo dos foreign keys de referencia; se escribe con `<relacion>_ids` del padre (§23) | — | — | — | — | — |
| Enum | Valores que nunca cambian en producción: `Enum` de Python en `shared/enums.py`, sin tabla | — | — | — | — | — |

Además, todo tipo con schemas tiene:

- **Auditar**, siempre, con su propia ruta `GET /{id}/audit` (§23), incluso
  si el tipo no tiene ninguna otra ruta. Es solo lectura, así que no abre un
  segundo camino de escritura.
- **Ser referenciado**, si otra tabla lo referencia. El Catálogo lo tiene
  siempre.
- **Lectura anónima**, si lo ve un visitante anónimo.

Reglas:

- Si un model encaja en dos tipos, gana el que describe cómo lo edita el
  usuario. Por ejemplo, las monedas son valores que otras tablas eligen
  (Catálogo), pero si vienen sembradas y el usuario solo ajusta su orden o
  visibilidad, son Filas fijas.
- Entre Extensión 1:1 y Extensión 1:1 embebida decide una pregunta: ¿se edita
  en el mismo formulario y con el mismo permiso que el padre? Sí → embebida;
  no → Extensión 1:1. El número de campos no influye.
- Cada operación tiene un solo camino: lo que ocurre en el padre no tiene
  ruta propia, y lo que tiene ruta propia no se escribe desde el padre.
- Una Extensión 1:1 nunca se elimina sola: cae en cascada con su padre (§19).
- **Singleton por dueño** (0 o 1 por usuario): por defecto como en la tabla,
  creado automáticamente. Crear = ruta solo si el dueño lo crea una vez;
  Listar = ruta solo si hay panel de administración.
- **Catálogo por dueño:** el service valida que la referencia elegida
  pertenezca al mismo dueño.

### Relaciones

Cada relación se clasifica con dos preguntas.

**1. ¿La apunto o la contengo?**

```text
apunto (referencia) → el otro registro existe por sí mismo; solo guardo su id
contengo (dueño)    → el otro registro es parte de mí: no existe sin mí, nunca
                      cambia de padre y se elimina en cascada conmigo (§19)
```

Prueba: si en Python se escribiría `padre.hijos.append(obj)`, la foreign key es
de dueño; si se escribiría `Obj(campo=VALOR_COMPARTIDO)`, como quien elige un
miembro de un `Enum`, es de referencia. En una línea de pedido, `pedido_id` es
de dueño y `producto_id` es de referencia.

**2. ¿Cuántos?** Uno, pocos o muchos. Es "pocos" si a la lista se le puede
poner un `max_length` razonable sin que el negocio lo rechace; si no, es
"muchos".

| Relación | Ejemplo, desde un pedido | El otro model es | Foreign key |
|---|---|---|---|
| Apunto a uno (N:1) | cliente | cualquier tipo | `cliente_id` en el pedido |
| Contengo uno (1:1) | dirección de envío | Extensión 1:1 (embebida o no) | el `id` de la dirección es el `id` del pedido (§18) |
| Contengo pocos (1:N) | líneas | Hija embebida | `pedido_id` en la línea; la asigna el service |
| Contengo muchos (1:N) | pagos | Hija paginada | `pedido_id` en el pago; obligatoria en su `Create` |
| Apunto a varios (N:M) | etiquetas | Puente N:M | las dos foreign keys en el puente |
| Me apuntan (inversa) | desde un cliente, sus pedidos | — | en el otro model |

- **N:M con datos propios** (por ejemplo, producto–proveedor con un precio):
  no es un Puente. Es una hija del extremo que la edita, embebida o paginada
  según la pregunta 2, con una referencia ("apunto a uno") al otro extremo.
  En un Puente N:M, en cambio, ambas foreign keys son de referencia.
- **Jerarquía autorreferenciada:** la foreign key de dueño apunta al mismo
  model.

---

## 18. Models

Los models persistentes usan SQLModel con `table=True` y heredan de
`BaseModel` (`core/base_model.py`, sin `table=True`), que aporta:

```text
id
created_at
created_by
updated_at
updated_by
is_deleted
deleted_at
deleted_by
```

Los models definen solo:

- columnas, primary keys y foreign keys;
- relaciones;
- índices;
- `nullable`;
- unicidad, como índice único parcial sobre registros no eliminados (§19);
- restricciones persistentes.

No contienen lógica HTTP ni reglas funcionales de negocio.

Las relaciones que necesitan los schemas con embebidos se declaran con
`Relationship()` y carga lazy deshabilitada (`lazy="raise"`): la sesión es
async y una carga implícita fallaría. El repository las carga explícitamente
(§22). Un `Relationship()` no crea columnas ni requiere migration.

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domains.lineas.models import LineaPedido


class Pedido(BaseModel, table=True):
    cliente_id: UUID = Field(foreign_key="clientes.id")
    lineas: list["LineaPedido"] = Relationship(
        sa_relationship_kwargs={"lazy": "raise"},
    )
```

- En SQLModel, `lazy` va dentro de `sa_relationship_kwargs`.
- Un model de otro dominio se anota entre comillas y se importa solo bajo
  `TYPE_CHECKING`, para evitar imports circulares entre dominios.

Una Extensión 1:1 (§17), embebida o no, usa como `id` el `id` de su padre: es a
la vez su primary key y su foreign key de dueño, y la base garantiza así que no
haya dos por padre. El service lo asigna al crearla; no se genera.

```python
class DatosFiscales(BaseModel, table=True):
    id: UUID = Field(foreign_key="clientes.id", primary_key=True)
```

---

## 19. Soft delete y auditoría

La eliminación estándar es lógica. `delete` actualiza:

```text
is_deleted = True
deleted_at
deleted_by
updated_at
updated_by
```

- `get` y `list` excluyen por defecto los registros con `is_deleted=True`. La
  consulta de eliminados es siempre explícita.
- Los services asignan `created_*`, `updated_*` y `deleted_*` cuando
  corresponda.

### Consulta de auditoría

`GET /{id}/audit` es la consulta explícita de eliminados del CRUD estándar:
devuelve el registro esté eliminado o no, para que su `deleted_at` y
`deleted_by` puedan consultarse.

- Reutiliza el mismo `get` del service, con `include_deleted=True`, que se pasa
  al repository.
- El valor por defecto es `False`: `GET /{id}`, `PATCH`, `DELETE` y el resto de
  operaciones responden `404` ante un registro eliminado.
- El parámetro solo desactiva el filtro de soft delete; el alcance de datos
  (§24) se sigue aplicando.

### Unicidad con soft delete

La unicidad solo se exige entre registros no eliminados: un registro eliminado
no impide que otro reutilice su valor.

- El service la valida consultando solo registros con `is_deleted=False` y
  responde `409` si ya existe uno con ese valor.
- En el model se declara como índice único parcial, nunca con `unique=True`
  en el campo, que en PostgreSQL incluiría también los registros eliminados:

```python
# ❌ No: incluye también los registros eliminados
email: str = Field(unique=True)

# ✅ Sí: índice único parcial, solo sobre registros no eliminados
__table_args__ = (
    Index(
        "uq_<tabla>_<campo>_not_deleted",
        "<campo>",
        unique=True,
        postgresql_where=text("is_deleted = false"),
    ),
)
```

La validación del service da el error claro; el índice protege ante
condiciones de carrera.

### Eliminación con dependientes

Lo que ocurre con los registros que dependen del eliminado lo determina el tipo
de foreign key con que lo apuntan (§17):

| Quién lo apunta | Qué ocurre |
|---|---|
| Hijos (foreign key de dueño): hijas embebidas, hijas paginadas, extensión 1:1 | Se eliminan lógicamente en cascada, con todos sus descendientes, en la misma transacción y con los mismos `deleted_at` y `deleted_by`. Solo afecta a los no eliminados |
| Registros que lo usan como referencia | Bloquean la eliminación con `409` mientras no estén eliminados. Para retirar un registro compartido sin eliminarlo se usa `is_visible` u otro estado equivalente |
| Registros inmutables (kardex) | Nunca se eliminan en cascada, porque no admiten `UPDATE`. Su foreign key cuenta como referencia aunque apunte a su dueño y bloquea con `409`. El registro al que apuntan, por ejemplo una tarjeta con movimientos, se retira con un estado (`status`) |
| Puentes N:M | Se eliminan lógicamente en cascada al eliminar cualquiera de sus extremos |
| Hijos en una jerarquía autorreferenciada | Bloquean la eliminación mientras no estén eliminados |

- Las mismas reglas aplican cuando la sincronización de un `UpdateNested`
  (§20) elimina un hijo.
- La cascada la coordina el service del registro eliminado; los repositories
  exponen las operaciones de marcado y no hacen commit.
- No se usa `ON DELETE CASCADE`: con eliminación lógica no hay borrado físico
  que propagar.
- Una referencia queda libre cuando los registros que la usaban se eliminan,
  incluso si fue por una cascada.

### Registros inmutables (kardex)

Un model de tipo Registro (§17), como un kardex o un libro de movimientos, no
usa soft delete: nada se edita ni se elimina, y todo cambio queda como una fila
nueva.

- **Solo `INSERT`.** Un trigger de PostgreSQL, creado en la migration, rechaza
  todo `UPDATE` y `DELETE` sobre la tabla, para que la regla no dependa del
  código. Hereda `BaseModel` completo; `updated_*` y `deleted_*` nunca se usan.
  Como no hay registros eliminados, sus índices únicos no necesitan ser
  parciales.
- **Anular es insertar un asiento de reverso:** `reverses_id` apunta al
  original y su importe tiene el signo contrario. El original no se toca. Un
  índice único sobre `reverses_id` impide anular dos veces el mismo asiento.
- **Corregir es anular e insertar el asiento correcto**, en la misma
  transacción.
- **Saldo sin condiciones de carrera:** cada asiento guarda `balance_after`. Al
  insertar, el service bloquea con `SELECT ... FOR UPDATE` la fila cuyo saldo
  se mueve (por ejemplo, la tarjeta), para que dos operaciones simultáneas no
  calculen sobre el mismo saldo.
- **Idempotencia:** `idempotency_key` con índice único, para que un reintento
  no registre la misma operación dos veces.
- **Datos que el cliente no controla:** `created_by` sale del actor
  autenticado y `created_at` de la base de datos (`now()`), nunca del body.
- **Importes** como `Numeric` o en centavos enteros, nunca como `float`.
- No expone `PATCH /{id}` ni `DELETE /{id}`; la anulación es un endpoint de
  acción (`POST /{id}/anular`) con el permiso `Action.DELETE` (§24).

---

## 20. Schemas

Todos los schemas de dominio heredan de `SchemaBase`, definido en
`shared/schemas/base.py`:

```python
class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
```

- `extra="forbid"` rechaza los campos que el schema no declara.
- La normalización de valores no se configura en `SchemaBase`: la aplican los
  validadores de `shared/services/validators.py` (§21).
- No existe un schema base por model (`<X>Base`): cada schema declara sus
  campos directamente.
- `AuditMixin`, en el mismo archivo, declara los campos que solo expone
  `<X>ResponseAudit`: `created_by`, `updated_by`, `is_deleted`, `deleted_at` y
  `deleted_by`.

### Catálogo de schemas

| Schema | Qué es | Hereda de |
|---|---|---|
| `<X>Create` | Crear plano: columnas y foreign keys de referencia como id. Sin `id`, auditoría ni campos que asigna el service | `SchemaBase` |
| `<X>CreateNested` | `<X>Create` + hijas embebidas + extensión 1:1 + relaciones N:M, en una sola transacción | `<X>Create` |
| `<X>Update` | Update plano: columnas modificables, todas opcionales | `SchemaBase` |
| `<X>UpdateNested` | `<X>Update` + hijas embebidas sincronizadas + extensión 1:1 embebida + relaciones N:M | `<X>Update` |
| `<X>NestedItem` | Elemento de una lista sincronizada: el hijo con `id` opcional | `<X>Create` o `<X>CreateNested` |
| `<X>Response` | Response plano: `id`, `created_at`, `updated_at` + columnas + foreign keys como id. No embebe nada | `SchemaBase` |
| `<X>ResponseAudit` | `<X>Response` + los campos de `AuditMixin` | `AuditMixin, <X>Response`, en ese orden |
| `<X>Ref` | Referencia mínima: `id` + el campo con que una persona identifica el registro (`name`, `title`, `code`…) | `SchemaBase` |
| `<X>ResponseItemList` | Fila de un listado | `<X>Response` |
| `<X>ResponseDetail` | Registro individual con su árbol | `<X>Response` |
| `<X>Public` | Vista para un visitante anónimo: solo lo visible, sin auditoría (§24) | `SchemaBase`, nunca `<X>Response` |

Se permiten schemas especiales para una operación funcional distinta, por
ejemplo `UserUpdateMe`, `ChangePassword` o `ResetPassword`, solo en el dominio
que los necesita.

### Reglas de schemas

- Cada schema acepta siempre los mismos campos.
- Los planos (`Create`, `Update`, `Response`) nunca contienen relaciones; las
  relaciones van solo en los Nested, `ResponseItemList` y `ResponseDetail`.
- La herencia es la de la columna "Hereda de": una salida nunca hereda de una
  entrada, ni al revés. `<X>ResponseAudit` nunca se hereda ni se embebe.
- `<X>ResponseAudit` hereda `(AuditMixin, <X>Response)` en ese orden: Pydantic
  ordena los campos según la herencia, y así la auditoría queda al final.
- Los campos de relación se llaman igual que la `Relationship()` del model. En
  las entradas, las relaciones N:M se envían como `<relacion>_ids`.
- Ningún update cambia `id`, la foreign key de dueño ni un campo de estado
  (`status`). El estado cambia solo mediante endpoints de acción (§24). Mover
  un nodo de una jerarquía autorreferenciada también es un endpoint de acción.

### Qué schemas tiene un model

Cada operación tiene una versión plana y otra con relaciones. Las columnas son
las rondas de §25:

| Operación | Plano (ronda 1) | Con relaciones (ronda 2) |
|---|---|---|
| Leer uno | `Response` | `ResponseDetail` |
| Listar | `Response` | `ResponseItemList` |
| Crear | `Create` | `CreateNested` |
| Editar | `Update` | `UpdateNested` |
| Editar en una lista del padre | — | `NestedItem` |
| Auditar | `ResponseAudit` | `ResponseAudit` |
| Ser referenciado | `Ref` | — |
| Lectura anónima | `Public` | — |

Se decide en dos pasos, siempre antes de las rutas:

1. **Operaciones:** toda celda de la fila del tipo (§17) que no sea "—",
   sea ruta, padre o interno: la operación existe y necesita su schema.
   Eliminar no tiene schema.
2. **Versión:** una operación usa la versión con relaciones si al menos una
   relación del model aparece en esa columna de la tabla de relaciones de
   abajo; si ninguna aparece, usa la plana. El Editar de una Hija embebida es
   siempre un elemento de la lista del padre: usa `NestedItem`.

Ejemplo: un pedido (Raíz) que referencia a un cliente y tiene líneas, y una
línea (Hija embebida) que referencia a un producto y no tiene nietos:

```text
Pedido
  Leer uno  ruta + relaciones   → PedidoResponseDetail
  Listar    ruta + relaciones   → PedidoResponseItemList
  Crear     ruta + relaciones   → PedidoCreateNested  (y su base PedidoCreate)
  Editar    ruta + relaciones   → PedidoUpdateNested  (y su base PedidoUpdate)
  Auditar                       → PedidoResponseAudit (y su base PedidoResponse)

Línea
  Leer uno  padre + relaciones  → LineaResponseDetail
  Crear     padre, plano        → LineaCreate
  Editar    padre, en la lista  → LineaNestedItem
  Auditar                       → LineaResponseAudit  (y su base LineaResponse)
```

### Tabla de relaciones

Cada relación (§17) aparece así en cada schema, desde un pedido:

| Relación | `Create` / `Update` | `CreateNested` | `UpdateNested` | `ResponseItemList` | `ResponseDetail` |
|---|---|---|---|---|---|
| Apunto a uno: cliente | `cliente_id` | — | — | `cliente: ClienteRef` | `cliente: ClienteResponse` |
| Contengo uno: dirección (embebida) | — | `direccion: DireccionCreate` | `direccion: DireccionUpdate \| None` | — | `direccion: DireccionResponse` |
| Contengo pocos: líneas | — | `lineas: list[LineaCreate]` | `lineas: list[LineaNestedItem] \| None` | resumen opcional | `lineas: list[LineaResponseDetail]` |
| Contengo muchos: pagos | `pedido_id` (en el `Create` del pago) | — | — | resumen opcional | — |
| Apunto a varios: etiquetas | — | `etiqueta_ids: list[id]` | `etiqueta_ids: list[id] \| None` | — | `etiquetas: list[EtiquetaRef]` |
| Me apuntan: desde un cliente, sus pedidos | — | — | — | — | — |

- **Contengo muchos** y **me apuntan** nunca se embeben: se consultan con un
  filtro en el listado del otro lado, por ejemplo `GET /pagos?pedido_id=` o
  `GET /pedidos?cliente_id=`. El `Create` de la hija paginada lleva la foreign
  key de dueño, obligatoria; su `Update` nunca la incluye.
- **Contengo pocos:** el `Create` de la hija embebida no lleva la foreign key
  de dueño; la asigna el service. Si cada hijo tiene a su vez nietos o
  referencias, se usan sus versiones con relaciones: `<Hijo>CreateNested` al
  crear y `<Hijo>ResponseDetail` al leer.
- **Contengo uno:** en `CreateNested` el campo es obligatorio si la extensión
  tiene columnas obligatorias sin valor por defecto; si no, es opcional y el
  service la crea con los valores por defecto. En `UpdateNested`, ausente o
  `null` significa no tocar: una extensión 1:1 no se elimina mientras exista
  su padre. Una Extensión 1:1 no embebida solo aparece en `CreateNested`: se
  lee y se edita con sus propias rutas (§17).
- Un **resumen** es un campo calculado (un conteo o un total) que excluye los
  registros eliminados. `ResponseItemList` nunca contiene colecciones.

### Profundidad y restricciones

```text
hacia abajo   (dueño → hijas embebidas) → hasta las hojas del árbol
hacia un lado (referencia)              → un solo paso; termina en un schema plano
hacia arriba  (hija → dueño)            → nunca
```

- El `ResponseDetail` embebe exactamente el árbol que acepta su
  `UpdateNested`: el cliente recibe lo mismo que después envía.
- Una referencia se embebe con el `Response` plano del referenciado, nunca con
  su `ResponseDetail`: ese árbol le pertenece al referenciado.
- La foreign key de dueño nunca se embebe; permanece como id.
- En una jerarquía autorreferenciada, el `ResponseDetail` embebe los hijos
  directos como `<X>Response`, un solo nivel. La jerarquía completa se expone
  con los schemas de `shared/schemas/tree.py` en un endpoint propio.
- Todo elemento embebido excluye los registros con `is_deleted=True`. En
  endpoints públicos aplica además las reglas de visibilidad del dominio.

### Escritura del árbol

Un model que contiene uno o pocos, o que apunta a varios, se escribe por un
solo camino: `POST /` recibe `<X>CreateNested` y `PATCH /{id}` recibe
`<X>UpdateNested`. Cada elemento de una lista de hijas embebidas es un
`<Hijo>NestedItem`:

```text
<Hijo>NestedItem  → <Hijo>Create (<Hijo>CreateNested si tiene nietos)
                    + id opcional
                    + sus nietos como list[<Nieto>NestedItem]
```

El schema valida la estructura: `max_length` en cada lista, ids repetidos
dentro de una misma lista y `<relacion>_ids` deduplicados.

En un `UpdateNested`, cada lista es el estado final deseado:

| Se envía | Resultado |
|---|---|
| Lista ausente o `null` | No se toca; en las listas `None` significa no tocar, no vaciar |
| `[]` | Se eliminan lógicamente todos los elementos |
| Elemento con `id` | Se actualiza; si no cambió nada, no se toca |
| Elemento sin `id` | Se crea |
| Hijo existente que no viene en la lista | Se elimina lógicamente, con cascada a sus nietos (§19). Por eso el cliente envía siempre la lista completa |

`<relacion>_ids` aplica la misma regla a los enlaces N:M. Si un producto tenía
las categorías `[A, C]` y se envía `{"categoria_ids": [A, B]}`: `A` se
conserva con su auditoría original, `C` se elimina lógicamente y `B` se crea.
Repetir la misma petición no produce cambios.

Cómo lo procesa el service: §22.

### Campos de `Update`

Todo campo modificable se declara con el tipo de su columna y `default=None`;
nunca se agrega `| None` a una columna no nullable. Su validador decide primero
el `None` y después delega en su función `object → T` (§21). Un campo omitido
no se modifica, porque el service usa `exclude_unset=True` (§22).

```python
class ClienteUpdate(SchemaBase):
    name: str = Field(default=None)           # columna no nullable
    phone: str | None = Field(default=None)   # columna nullable

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        if value is None:
            raise ValueError("El nombre no puede ser null.")   # null → 422
        return validator_name(value)

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, value: object) -> str | None:
        if value is None:
            return None                                         # null → se borra
        return validator_phone(value)
```

### Ejemplos de documentación

Todo schema expuesto en la API define un ejemplo:

```python
model_config = ConfigDict(json_schema_extra={"example": {...}})
```

El ejemplo:

- contiene todos los campos del schema, incluidos los heredados y los
  embebidos, en el orden en que se declaran;
- no contiene valores `null`: un campo nullable se muestra con un valor de
  ejemplo, porque el ejemplo documenta el tipo; la pestaña Schema de la
  documentación indica qué campos admiten `null`;
- pasa la validación de su propio schema;
- es coherente entre campos; por ejemplo, un `<X>ResponseAudit` con
  `deleted_at` tiene `is_deleted: true`.

`core/openapi.py` conserva estos ejemplos tal como están escritos, con su
orden, al generar la documentación.

---

## 21. Validaciones

Cada capa valida lo suyo:

| Capa | Valida |
|---|---|
| Schema | Formato, estructura y normalización |
| Service | Reglas de negocio y validaciones que consultan la base de datos |
| Repository | Nada: ejecuta queries y operaciones de persistencia |
| Model / PostgreSQL | Integridad persistente |
| Integration | Restricciones técnicas para proteger o usar al proveedor externo |

Los validadores reutilizables sin acceso a base de datos viven en
`shared/services/validators.py` y siguen esta firma:

```text
object → T
```

- Reciben el valor como `object`, comprueban su tipo en tiempo de ejecución y
  devuelven un valor concreto validado o normalizado.
- Si el tipo no es válido, lanzan `ValueError`; no usan métodos del tipo
  esperado antes de comprobarlo.
- En los schemas se usan siempre con `field_validator(mode="before")`, para
  recibir el valor tal como llegó; con `mode="after"`, Pydantic ya habría
  convertido, por ejemplo, `"true"` en `True`.
- Nunca devuelven `None`: qué hacer con un `None` lo decide el
  `field_validator` del schema (§20, "Campos de `Update`").

Todo campo de entrada (`Create`, `Update`, `NestedItem`) tiene su
`field_validator`, salvo los ids y los `Enum`, que ya valida Pydantic. Sin
validador, Pydantic convierte valores en silencio (`"true"` → `True`) y no
normaliza.

`Field(...)` y el validador no se reparten el mismo límite:

- `Field(...)` declara los límites que dependen de la columna o del schema:
  `max_length` igual al de la columna (`String(n)`), rangos con `ge`/`le` y
  `max_length` de listas. Aparecen en la documentación y se comprueban sobre
  el valor ya normalizado.
- El validador comprueba tipo, formato y normalización, y las reglas que valen
  en cualquier schema, como la longitud de una contraseña.

---

## 22. Services

Los services contienen:

- lógica de negocio;
- coordinación de repositories e integrations;
- transacciones: el service controla `commit()` y `rollback()` para coordinar
  varios repositories en una misma transacción;
- validaciones con base de datos;
- asignación de campos de auditoría (§19).

CRUD estándar: `get`, `list`, `create`, `update` y `delete` (soft delete).

### Actualizaciones parciales

Un `PATCH` se procesa con:

```python
model_dump(exclude_unset=True)
```

Nunca con `exclude_none=True`: eliminaría también los `None` enviados
explícitamente y haría imposible limpiar campos nullable. Los valores
explícitos `0` y `False` tampoco se descartan.

### Referencias recibidas

Toda foreign key de referencia que envía el cliente (`<x>_id`,
`<relacion>_ids`) se valida en el service antes de guardar: el registro existe,
no está eliminado y está dentro del alcance del actor (§24). Si no, `422`.

A diferencia de las comprobaciones de integridad del §24, esta sí aplica el
alcance: enlazar un registro es una acción del actor, y sin el alcance podría
enlazar registros ajenos conociendo su id.

### Escritura con Nested

Al procesar un `CreateNested` o un `UpdateNested` (§20):

- Un `id` que no pertenece a ese padre o que está eliminado se rechaza con
  `422`. Sin esta comprobación, un cliente podría modificar hijos de otro
  padre.
- Eliminar un hijo que otro registro referencia bloquea la operación con `409`
  (§19) y no se aplica ningún cambio.
- Cada hijo y cada id de `<relacion>_ids` se validan con las mismas reglas de
  negocio que una creación individual.
- Todo ocurre en una sola transacción, en este orden: eliminar, `flush()` para
  liberar los índices únicos parciales (§19), actualizar y crear. Ese
  `flush()` lo hace el service sobre la sesión, porque controla la
  transacción.
- El cálculo de qué actualizar, crear y eliminar es una función pura de
  `shared/services/sync.py`, que reutilizan todos los services.

### Repositories

Cada dominio persistente encapsula el acceso a datos en `repositories.py`. Los
repositories:

- construyen y ejecutan queries con SQLModel y SQLAlchemy;
- reciben o utilizan `AsyncSession`;
- recuperan y persisten models;
- aplican filtros, orden, paginación, condiciones de soft delete y el alcance
  (§24) solicitados por el service;
- cargan explícitamente las relaciones que requiere cada `ResponseItemList` y
  `ResponseDetail`, por ejemplo con `selectinload`, excluyendo también los
  embebidos eliminados;
- pueden usar `flush()` y `refresh()` cuando la operación lo requiera.

No contienen reglas de negocio, decisiones HTTP, schemas de API ni llamadas a
integrations, y nunca hacen `commit()` ni `rollback()`.

No se crea un repository genérico ni una clase base por defecto: cada
repository expone operaciones explícitas que respondan a necesidades reales del
dominio.

---

## 23. Routes

Las routes gestionan únicamente:

- HTTP;
- `Depends`;
- path/query parameters;
- schemas;
- status codes;
- llamada al service.

Cada dominio expone un router con el recurso en plural, en minúsculas y con
guiones:

```python
router = APIRouter(prefix="/datos-fiscales", tags=["Datos fiscales"])
```

### CRUD estándar

Solo las celdas **ruta** de la tabla de tipos (§17) tienen endpoint; las
celdas padre e interno no tienen ninguno:

| Operación | Ruta | Código |
|---|---|---|
| Listar | `GET /` | `200` |
| Leer uno | `GET /{id}` | `200` |
| Auditar | `GET /{id}/audit`, en todo tipo con schemas (§17) | `200` |
| Crear | `POST /` | `201` |
| Editar | `PATCH /{id}` | `200` |
| Eliminar | `DELETE /{id}` | `204`, sin cuerpo |

Cada endpoint usa el schema que corresponde al model (§20): la versión con
relaciones si el model la tiene, y la plana si no. En `POST` y `PATCH` se
indica `entrada → respuesta`:

```text
                  con relaciones                            plano
GET /             PaginatedResponse[<X>ResponseItemList]    PaginatedResponse[<X>Response]
GET /{id}         <X>ResponseDetail                         <X>Response
GET /{id}/audit   <X>ResponseAudit                          <X>ResponseAudit
POST /            <X>CreateNested → <X>ResponseDetail       <X>Create → <X>Response
PATCH /{id}       <X>UpdateNested → <X>ResponseDetail       <X>Update → <X>Response
```

- `POST /` y `PATCH /{id}` responden lo mismo que `GET /{id}`, para que el
  cliente reciba el registro creado o actualizado sin otra consulta. El service
  lo recarga con su `ResponseDetail` después del commit; en un `PATCH`, también
  cuando no hay cambios.
- Las operaciones que no crean ni modifican un recurso por su id, como subir un
  archivo o emitir tokens, conservan su propia respuesta.
- `GET /{id}/audit` reutiliza el mismo `get` que `GET /{id}`, con
  `include_deleted=True` (§19). Solo cambian el `response_model`, los permisos,
  la información expuesta y las relaciones que carga el repository.
- `GET /me` y `PATCH /me` reutilizan `get` y `update` cuando la lógica sea
  equivalente.

### Listados

`GET /` recibe la paginación y los filtros como query parameters:

```python
@router.get(
    "/",
    response_model=PaginatedResponse[UserResponse],
    summary="Listar usuarios",
    responses=error_responses(401, 403, 422, 500),
)
async def list_users(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.USUARIO, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    sucursal_id: Annotated[UUID | None, Query()] = None,
    role: Annotated[Role | None, Query()] = None,
) -> PaginatedResponse[UserResponse]:
    return await UserService.list(
        db_session,
        actor=current_user,
        page=page,
        per_page=per_page,
        sucursal_id=sucursal_id,
        role=role,
    )
```

- `page` empieza en 1; `per_page` vale 20 por defecto y como máximo 100.
- Cada filtro es opcional (`None` = sin filtrar) y se llama como el campo que
  filtra, por ejemplo `pedido_id` para listar las hijas paginadas de un padre.
- El service recibe al actor para aplicar el alcance (§24).
- Todo endpoint documenta sus errores posibles con `error_responses(...)` de
  `shared/schemas/errors.py`.
- Sin un orden pedido, el listado se ordena por `created_at` descendente. Un
  orden propio del dominio es un query parameter explícito, como
  `order_by_points: bool = False`.

### Endpoints de acción

Lo que no es un `PATCH` de campos (cambiar un `status`, anular un asiento de un
Registro, mover un nodo de una jerarquía) es un endpoint de acción:

```text
POST /{id}/<accion>     → POST /pedidos/{id}/confirmar, POST /movimientos/{id}/anular
```

- La acción es un verbo en infinitivo, en minúsculas y con guiones.
- Recibe un schema especial solo si la acción necesita datos.
- Responde `200` con lo mismo que `GET /{id}`.
- Su permiso es la `Action` que representa (§24), por ejemplo `UPDATE`.

### Tablas de enlace N:M

Un Puente N:M (§17) no se expone como recurso: no tiene schemas ni rutas.

- Se escribe desde un solo extremo, con `<relacion>_ids` en su `POST /` y su
  `PATCH /{id}`; el otro extremo nunca lo escribe. Es el extremo con pocos
  enlaces por registro (pregunta 2 del §17); si ambos tienen pocos, el que lo
  edita en la práctica. Por ejemplo, `PATCH /productos/{id}` con
  `{"categoria_ids": [A, B]}`.
- El otro extremo lo lee con un filtro, como `GET /productos?categoria_id=`.
- Si ambos extremos tienen muchos enlaces, no es un Puente: es una Hija
  paginada con rutas propias, como `POST /inscripciones`.
- El dominio de enlace conserva su model y su repository; el service del padre
  los coordina.

---

## 24. Security

`core/security.py` contiene solo primitivas reutilizables: password hashing,
JWT, refresh tokens, CSRF y one-time tokens. No contiene login, logout,
sesiones, consultas de usuarios, roles, permisos, `Depends`, cookies ni
respuestas HTTP.

`SECRET_KEY` y `CSRF_SECRET_KEY` deben ser diferentes.

### Roles y permisos

`shared/services/permissions.py` es la única fuente de verdad de la
autorización:

```text
ROLE_PERMISSIONS                → acciones que cada rol puede ejecutar en cada módulo
ROLE_LEVEL                      → jerarquía de roles; un número mayor es un rango superior
<MODULO>_<ALCANCE>_SCOPE_ROLES  → grupos de roles por alcance de datos, cuando existan
```

Expone:

```python
has_permission(role, module, action) -> bool
can_manage_role(actor_role, target_role) -> bool
```

Agregar un rol exige declararlo en `Role` (`shared/enums.py`) y actualizar
todas las estructuras de `permissions.py`, y nada más.

### Niveles de acceso

Cada endpoint pertenece a exactamente uno de estos niveles, evaluados en orden:

```text
1. Pública              → sin dependencia de usuario
2. Recurso propio (/me) → get_current_principal
3. Capacidad de módulo  → require_permission(Module, Action)   ← por defecto
4. Vista de un rol      → require_role(...)                    ← excepción
```

- **Pública:** endpoints abiertos sin login, como la autenticación (login,
  registro, refresh, recuperación de contraseña), los endpoints de sistema
  (health) y las lecturas públicas que defina un dominio, por ejemplo un
  catálogo. Una lectura pública aplica las reglas de visibilidad del dominio y
  nunca expone campos de auditoría. Si su respuesta cambia cuando hay un
  usuario autenticado, usa `get_current_principal_optional`. Los endpoints
  públicos que reciben credenciales o datos del cliente deben tener rate limit.
- **`/me`:** no verifica permisos por módulo, porque su autorización es la
  identidad: solo opera sobre el usuario autenticado. El id del recurso se
  obtiene únicamente de `current_user.id`; nunca se acepta un id del path,
  query o body. Así, un rol sin acceso al módulo de usuarios puede consultar y
  editar su propio perfil y cambiar su contraseña.
- **`require_permission`:** opción por defecto para toda operación sobre un
  recurso de un módulo, sea CRUD o no.
- **`require_role`:** solo cuando el endpoint está definido por el rol, es
  decir, su respuesta o flujo no tiene sentido para otro rol (por ejemplo,
  dashboards o resúmenes de inicio por rol).

Para elegir entre `require_permission` y `require_role`:

> Si mañana se crea un rol nuevo, ¿debería poder darse acceso a este endpoint
> modificando solo la matriz de permisos?

- **Sí** → `require_permission`.
- **No**, porque el endpoint pertenece a un rol y otro rol necesitaría una
  vista distinta → `require_role`.

Las tareas del sistema (expirar registros, recalcular saldos) idealmente no se
exponen como endpoints, sino como jobs programados. Si deben exponerse, se
acepta `require_role` con los roles operativos explícitos.

### Las acciones son capacidades, no métodos HTTP

`Action` representa lo que el rol puede hacer, no el verbo HTTP del endpoint:

```text
POST /recurso/{id}/confirmar  → UPDATE
POST /recurso/{id}/cancelar   → UPDATE
POST /recurso/{id}/imagen     → UPDATE
POST /recurso/{id}/anular     → DELETE   (retira su efecto; el registro no se borra)
POST /recurso/sugerir-valor   → CREATE   (ayuda previa a crear)
GET  /recurso/{id}/audit      → AUDIT
```

Anular usa `DELETE` y no `UPDATE` para que editar un registro no dé también
permiso para anularlo.

### Matriz de permisos

- `ROLE_PERMISSIONS` es la única fuente de verdad de `rol × módulo → acciones`.
- Todo model con schemas es un `Module` propio, también las hijas embebidas y
  las extensiones 1:1. Así, su `GET /{id}/audit` usa
  `require_permission(<Módulo>, Action.AUDIT)`. Una hija embebida o una
  extensión 1:1 aplica el alcance de su padre.
- Lo que una hija embebida o una extensión 1:1 hace dentro de su padre lo
  autoriza el permiso del padre (por ejemplo, `PEDIDO` + `UPDATE`). El módulo
  de la hija solo se usa en sus propias rutas, su `/audit` y sus endpoints de
  acción, y en la matriz solo lista esas acciones.
- Se deniega por defecto: un módulo ausente equivale a sin acceso.
- Cada rol lista todos los módulos, incluso los que no puede usar, para que la
  matriz se lea como una tabla.
- Los conjuntos de acciones son `frozenset`, escritos de forma explícita en
  cada entrada, aunque se repitan. No se usan constantes con nombre para
  agruparlos.
- El acceso vacío se escribe `frozenset()`. Nunca `{}`, que en Python es un
  `dict`.
- Una entrada con menos acciones que el resto lleva un comentario con su
  motivo de negocio.

```python
ROLE_PERMISSIONS: dict[Role, dict[Module, frozenset[Action]]] = {
    Role.EJEMPLO: {
        Module.A: frozenset({Action.READ, Action.UPDATE}),  # motivo de negocio
        Module.B: frozenset(),  # sin acceso
    },
}


def has_permission(role: Role, module: Module, action: Action) -> bool:
    return action in ROLE_PERMISSIONS.get(role, {}).get(module, frozenset())
```

### Alcance de datos (segunda puerta)

La autorización tiene dos puertas y ambas son obligatorias:

```text
1. Permiso → ¿este rol puede usar este endpoint?          → dependencia + matriz de permisos
2. Alcance → ¿qué filas puede ver o modificar este actor? → alcance resuelto por el service
```

La primera puerta no protege los datos: sin la segunda, un rol con `READ` sobre
un módulo puede leer todas sus filas.

El alcance no es lo mismo que la visibilidad del dominio (`is_visible`). La
visibilidad decide qué se muestra al público; el alcance decide qué filas
corresponden a cada actor autenticado.

**Cuándo un módulo necesita alcance.** Para cada módulo, y para cada rol que
tenga alguna acción sobre él en la matriz:

> ¿Este rol debe ver o modificar **todas** las filas del módulo?

- **Sí para todos los roles con acceso** → no necesita alcance.
- **No para al menos un rol** → necesita alcance, aplicado a todo lo que ese
  rol pueda leer o modificar.

**Reglas de implementación.**

1. **Una única resolución de alcance por módulo.** Recibe el actor
   (`CurrentUser`) y produce el alcance. La reutilizan todas las lecturas del
   módulo: `get`, `list`, `get_by_*` y `audit`. `CurrentUser` sale de los
   claims del access token; si el alcance necesita otro dato del actor, se
   agrega a los claims y a `CurrentUser`.
2. **Denegar por defecto.** Un rol no contemplado recibe un alcance vacío, que
   no devuelve ninguna fila. Nunca recibe un alcance "sin filtro".
3. **Las escrituras también se filtran.** `update`, `delete` y acciones como
   confirmar o cancelar buscan la fila con el mismo alcance. De lo contrario,
   un actor puede modificar registros ajenos si conoce su id.
4. **Los grupos de roles son constantes en `permissions.py`**, junto a la
   matriz, con el formato `<MODULO>_<ALCANCE>_SCOPE_ROLES`; por ejemplo,
   `ORDER_GLOBAL_SCOPE_ROLES` u `ORDER_BUSINESS_SCOPE_ROLES`.
   Nunca se escriben como condiciones sueltas repartidas por el código.
5. **Fuera de alcance = `404`; sin la acción = `403`.**
   - Si el actor no puede ver la fila, se responde que no existe, para no
     revelar su existencia.
   - Si la ve pero no puede ejecutar esa acción sobre ella, se responde `403`.
     Por ejemplo, la jerarquía de usuarios: un OWNER ve a un SUPERADMIN en el
     listado, pero no puede modificarlo.
6. **Un test por rol** comprueba que no obtiene ni modifica filas fuera de su
   alcance, igual que se prueba el `403` de la primera puerta.

Las comprobaciones de integridad no aplican el alcance, porque protegen los
datos y no la vista del actor. Consultan siempre todas las filas no eliminadas:

- la unicidad (§19), por ejemplo un `get_by_slug` usado para rechazar un
  duplicado;
- las referencias no eliminadas que bloquean una eliminación con `409` (§19);
- los hijos que se eliminan en cascada (§19).

**Dónde vive el alcance.**

> Los roles nunca bajan al repository. El SQL nunca sube al service.

```text
repositories.py → <Modulo>Scope: dataclass sin roles (business_id, all, ...)
                  contrato de entrada del repository: alcance → WHERE
services.py     → resolución del alcance a partir del actor: actor → <Modulo>Scope
```

La clase del alcance se define en el repository, que es quien la consume. Así,
el service la importa y el repository no importa al service (§4).

```python
# repositories.py: aplica el alcance, sin roles
@dataclass(frozen=True)
class OrderScope:
    business_id: UUID | None = None
    all: bool = False


# services.py: decide el alcance, sin SQL
def _scope_for(actor: CurrentUser) -> OrderScope:
    if actor.role in ORDER_GLOBAL_SCOPE_ROLES:
        return OrderScope(all=True)
    if actor.role in ORDER_BUSINESS_SCOPE_ROLES:
        return OrderScope(business_id=actor.business_id)
    return OrderScope()  # alcance vacío: no devuelve filas


order = await OrderRepository.get(db_session, order_id, scope=_scope_for(actor))
```

### Jerarquía de usuarios

El service de usuarios aplica además la jerarquía:

- un usuario solo puede crear, modificar, eliminar o restablecer la contraseña
  de usuarios con un rol estrictamente inferior al suyo; nunca de su mismo rol
  ni de uno superior;
- solo puede asignar roles estrictamente inferiores al suyo;
- al modificar un usuario se valida tanto su rol actual como el rol resultante;
- nadie puede cambiar su propio rol: los schemas y endpoints `/me` no aceptan
  el campo de rol;
- en consecuencia, el rol de mayor rango no es gestionable desde la API y se
  crea mediante seed;
- el rol de quien actúa se obtiene siempre del usuario autenticado en el
  servidor, nunca de datos enviados por el cliente.

Una violación de la jerarquía responde `403` con `ErrorCode.PERMISSION_DENIED`.

---

## 25. Orden de construcción de un backend nuevo

### Etapa horizontal: todos los dominios a la vez

1. Lectura de `database.md`, en la raíz del proyecto, que contiene el SQL de
   PostgreSQL de la base. Es la única fuente de tablas, columnas, tipos,
   nullables, unicidades y foreign keys: no se inventan tablas ni campos.
   - El SQL dice qué se guarda, no cómo se implementa: se aplican las reglas
     de este archivo. Los campos de `BaseModel` (§18) no se repiten, un
     `UNIQUE` pasa a índice único parcial (§19) y no se usa
     `ON DELETE CASCADE`.
   - El SQL no indica si una foreign key es de dueño o de referencia, ni si
     una lista es de pocos o de muchos. Con lo que deduce del SQL y de sus
     comentarios, el agente propone la clasificación de cada tabla y relación
     (§17) y la confirma con el usuario antes de crear los models.
2. Clasificación de todos los models (§17), ya confirmada.
3. Módulos en `Module`, matriz de permisos y alcance de cada módulo (§24).
4. Models de todas las tablas (§18), con sus `Relationship()`, y una única
   migración inicial (§8), completada a mano con los triggers de los Registros
   (§19) y las Filas fijas (§17).
5. Validadores reutilizables en `shared/services/validators.py`.
6. Schemas de todos los dominios (§20), en dos rondas que corresponden a las
   columnas de su cuadrícula:
   - Ronda 1, schemas planos: `Create`, `Update`, `Response`,
     `ResponseAudit`, `Ref` y `Public`.
   - Ronda 2, schemas con relaciones: `ResponseItemList`, `ResponseDetail`,
     `CreateNested`, `UpdateNested` y `NestedItem`.

   Cada ronda se valida con sus tests de schemas.

Esta etapa es horizontal porque todo lo que produce es declarativo y abarca
todos los dominios: un `ResponseDetail` embebe schemas de otros dominios, la
base de datos se diseña y migra completa de una vez, y la matriz de permisos
lista todos los módulos de cada rol.

### Etapa vertical: un dominio por vez

Cada dominio recibe su repository, service, routes, tests y prueba contra la
base de datos de desarrollo, en este orden:

1. Dominios sin foreign keys, completos.
2. Primera vuelta de los dominios con foreign keys, de padres a hijos. Un
   dominio se implementa cuando ya existen los dominios a los que apuntan sus
   foreign keys.
   - Las rutas que marca su tipo (§17).
   - `GET /` devuelve `PaginatedResponse[<X>Response]` y `GET /{id}` devuelve
     `<X>Response`.
   - Sin carga de embebidos.
   - Las hijas embebidas, los puentes N:M y las extensiones 1:1, embebidas o
     no, solo reciben su repository: se crean dentro de su padre, que todavía
     no los escribe.
3. Segunda vuelta de los dominios con foreign keys, de hijos a padres. Antes de
   empezarla existe `shared/services/sync.py` (§22).
   - El repository carga los embebidos.
   - `GET /` pasa a `PaginatedResponse[<X>ResponseItemList]` y `GET /{id}` a
     `<X>ResponseDetail`, en los tipos que los definan.
   - `POST /` y `PATCH /{id}` pasan a recibir `<X>CreateNested` y
     `<X>UpdateNested` y a responder `<X>ResponseDetail`, en los tipos que los
     definan. El service del padre coordina la escritura de sus hijas
     embebidas, su extensión 1:1 y sus enlaces N:M.
   - Las hijas embebidas y las extensiones 1:1 reciben su `GET /{id}/audit`, y
     la Extensión 1:1 no embebida, además, su `GET` y su `PATCH`.
   - Cada `ResponseDetail` se prueba con datos reales de todo su árbol.

La segunda vuelta no empieza hasta terminar la primera de todos los dominios:
el `ResponseDetail` de un dueño embebe a sus hijos, y solo puede probarse con
datos reales cuando todos sus hijos ya se pueden crear.

Un dominio sin hijos en otros dominios (solo referencias o jerarquía
autorreferenciada) puede completar ambas vueltas a la vez.

Entre ambas vueltas se acepta que los dominios con foreign keys no cumplan
todavía la tabla de schemas por endpoint de §23. El cambio posterior es
compatible, porque `<X>ResponseItemList` y `<X>ResponseDetail` heredan de
`<X>Response`.

Los cambios posteriores a la construcción inicial, como un campo o un dominio
nuevo, no repiten este orden: se aplican directamente en las capas afectadas,
con su propia migration.
