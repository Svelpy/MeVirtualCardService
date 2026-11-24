from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal_optional, require_permission, require_role
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.schemas import (
    TarjetaCreateNested,
    TarjetaPublic,
    TarjetaResponseAudit,
    TarjetaResponseDetail,
    TarjetaResponseItemList,
    TarjetaSlugDisponibleResponse,
    TarjetaUpdateNested,
    TarjetasDespublicadasResponse,
)
from app.domains.tarjeta.services import TarjetaService
from app.middlewares.limiter import limiter
from app.shared.enums import Action, Module, Role
from app.shared.schemas.errors import error_responses
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/tarjetas", tags=["Tarjetas"])


# ---------- Lectura anónima (§24) ----------
# Antes de /{tarjeta_id}, para que "public" no se lea como un id.

@router.get(
    "/public/slug-disponible/{slug}",
    response_model=TarjetaSlugDisponibleResponse,
    summary="Verificar si un slug está disponible",
    description=(
        "Sin login, para validar el slug mientras se escribe (me.svelpy.com/{slug}). Un slug con formato "
        "inválido (solo minúsculas, dígitos y guiones simples, de 3 a 80) responde 422. Con sesión, el "
        "slug actual de la tarjeta propia cuenta como disponible."
    ),
    responses=error_responses(401, 422, 429, 500),
)
@limiter.limit("30/minute")
async def slug_disponible(
    request: Request,
    slug: Annotated[str, Path(min_length=3, max_length=80, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")],
    current_user: Annotated[CurrentUser | None, Depends(get_current_principal_optional)],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaSlugDisponibleResponse:
    disponible = await TarjetaService.slug_disponible(db_session, slug, current_user)
    return TarjetaSlugDisponibleResponse(slug=slug, disponible=disponible)


@router.get(
    "/public/id/{tarjeta_id}",
    response_model=TarjetaPublic,
    summary="Ver una tarjeta publicada por su id (QR)",
    description=(
        "El QR codifica /t/{id}: el frontend la pide por id y redirige a su slug actual. Responde 404 si "
        "no está publicada, si su dueño está dado de baja o si su plan venció."
    ),
    responses=error_responses(404, 422, 500),
)
async def get_public_tarjeta_by_id(
    tarjeta_id: UUID,
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaPublic:
    return await TarjetaService.get_public(db_session, tarjeta_id=tarjeta_id)


@router.get(
    "/public/{slug}",
    response_model=TarjetaPublic,
    summary="Ver una tarjeta publicada",
    description="Todo su árbol, vitrina e items incluidos, solo con lo visible y sin auditoría.",
    responses=error_responses(404, 500),
)
async def get_public_tarjeta(
    slug: str,
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaPublic:
    return await TarjetaService.get_public(db_session, slug=slug)


# ---------- Tarea del sistema ----------

@router.post(
    "/despublicar-vencidas",
    response_model=TarjetasDespublicadasResponse,
    summary="Despublicar las tarjetas con el plan vencido",
    description=(
        "Lo mismo que hace el cron (jobs/despublicar_vencidas.py), a pedido de un admin. Se puede "
        "repetir: una tarjeta ya despublicada no se toca."
    ),
    responses=error_responses(401, 403, 500),
)
async def despublicar_vencidas(
    # Tarea del sistema (§24): require_role con los roles operativos, no la matriz.
    current_user: Annotated[CurrentUser, Depends(require_role(Role.SUPERADMIN, Role.ADMIN))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetasDespublicadasResponse:
    count = await TarjetaService.despublicar_vencidas(db_session, current_user)
    return TarjetasDespublicadasResponse(despublicadas=count)


# ---------- Gestión ----------


@router.get(
    "/",
    response_model=PaginatedResponse[TarjetaResponseItemList],
    summary="Listar tarjetas",
    description="Un admin ve todas; un usuario, solo la suya.",
    responses=error_responses(401, 403, 422, 500),
)
async def list_tarjetas(
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    user_id: Annotated[UUID | None, Query()] = None,
    is_public: Annotated[bool | None, Query()] = None,
) -> PaginatedResponse[TarjetaResponseItemList]:
    return await TarjetaService.list(
        db_session, current_user, page=page, per_page=per_page, user_id=user_id, is_public=is_public
    )


@router.get(
    "/{tarjeta_id}",
    response_model=TarjetaResponseDetail,
    summary="Obtener una tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def get_tarjeta(
    tarjeta_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaResponseDetail:
    return await TarjetaService.get(db_session, tarjeta_id, current_user)


@router.get(
    "/{tarjeta_id}/audit",
    response_model=TarjetaResponseAudit,
    summary="Auditar una tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_tarjeta(
    tarjeta_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaResponseAudit:
    return await TarjetaService.get(db_session, tarjeta_id, current_user, include_deleted=True)


@router.post(
    "/",
    response_model=TarjetaResponseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Crear mi tarjeta",
    description=(
        "Una por usuario, con su árbol en una sola transacción. Se crea despublicada; sin theme, seo o "
        "vitrina se crean con sus valores por defecto (theme claro) y las 8 secciones las crea siempre el "
        "sistema. Las URLs de imagen son las de POST /imagenes/uploads."
    ),
    responses=error_responses(401, 403, 409, 422, 500),
)
async def create_tarjeta(
    data: TarjetaCreateNested,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA, Action.CREATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TarjetaResponseDetail:
    return await TarjetaService.create(db_session, data, current_user, settings)


@router.patch(
    "/{tarjeta_id}",
    response_model=TarjetaResponseDetail,
    summary="Editar una tarjeta",
    description=(
        "Un campo que no se envía no cambia. Cada lista es el estado final: ausente o null no se toca, [] "
        "elimina todos sus elementos. Un elemento sin id se crea; con id, se actualiza; uno existente que "
        "no viene se elimina, por eso la lista se envía completa. secciones lleva siempre las 8 con su id. "
        "theme, seo y vitrina no se editan aquí: tienen su propio PATCH."
    ),
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
async def update_tarjeta(
    tarjeta_id: UUID,
    data: TarjetaUpdateNested,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TarjetaResponseDetail:
    return await TarjetaService.update(db_session, tarjeta_id, data, current_user, settings)


@router.delete(
    "/{tarjeta_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una tarjeta",
    description="Elimina también todo su árbol: theme, SEO, secciones, contactos, ubicaciones, vitrina...",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def delete_tarjeta(
    tarjeta_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA, Action.DELETE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await TarjetaService.delete(db_session, tarjeta_id, current_user)


@router.post(
    "/{tarjeta_id}/publicar",
    response_model=TarjetaResponseDetail,
    summary="Publicar una tarjeta",
    description="Exige que el dueño esté activo, tenga el email verificado y el plan vigente (409 si no).",
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
async def publicar_tarjeta(
    tarjeta_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaResponseDetail:
    return await TarjetaService.publicar(db_session, tarjeta_id, current_user)


@router.post(
    "/{tarjeta_id}/despublicar",
    response_model=TarjetaResponseDetail,
    summary="Despublicar una tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def despublicar_tarjeta(
    tarjeta_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaResponseDetail:
    return await TarjetaService.despublicar(db_session, tarjeta_id, current_user)
