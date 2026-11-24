from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal, require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.schemas import UsuarioResponseMe
from app.domains.usuario.schemas import (
    UsuarioCreate,
    UsuarioResponseAudit,
    UsuarioResponseDetail,
    UsuarioResponseItemList,
    UsuarioUpdate,
    UsuarioUpdateMe,
)
from app.domains.usuario.services import UsuarioService
from app.shared.enums import Action, Module, Role
from app.shared.schemas.errors import error_responses
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


# ---------- Recurso propio (/me): la autorización es la identidad (§24) ----------
# Antes de /{usuario_id}, para que "me" no se lea como un id.

@router.get(
    "/me",
    response_model=UsuarioResponseMe,
    summary="Obtener mi usuario",
    description=(
        "Mi usuario, mi plan y mi tarjeta completa como la ve su dueño: theme, seo, todas sus hijas "
        "(visibles y ocultas) y la vitrina con categorías, items e imágenes. tarjeta es null si "
        "todavía no la creé. Cada parte se edita en su propia ruta."
    ),
    responses=error_responses(401, 404, 500),
)
async def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UsuarioResponseMe:
    return await UsuarioService.get_me(db_session, current_user)


@router.patch(
    "/me",
    response_model=UsuarioResponseDetail,
    summary="Editar mi usuario",
    description="Cambiar el email lo deja sin verificar hasta usar el enlace de verificación.",
    responses=error_responses(401, 404, 409, 422, 500),
)
async def update_me(
    data: UsuarioUpdateMe,
    current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UsuarioResponseDetail:
    return await UsuarioService.update_me(db_session, data, current_user)


# ---------- Administración ----------

@router.get(
    "/",
    response_model=PaginatedResponse[UsuarioResponseItemList],
    summary="Listar usuarios",
    responses=error_responses(401, 403, 422, 500),
)
async def list_usuarios(
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    rol: Annotated[Role | None, Query()] = None,
    plan_id: Annotated[UUID | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> PaginatedResponse[UsuarioResponseItemList]:
    return await UsuarioService.list(
        db_session, page=page, per_page=per_page, rol=rol, plan_id=plan_id, is_active=is_active
    )


@router.get(
    "/{usuario_id}",
    response_model=UsuarioResponseDetail,
    summary="Obtener un usuario",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def get_usuario(
    usuario_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UsuarioResponseDetail:
    return await UsuarioService.get(db_session, usuario_id)


@router.get(
    "/{usuario_id}/audit",
    response_model=UsuarioResponseAudit,
    summary="Auditar un usuario",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_usuario(
    usuario_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UsuarioResponseAudit:
    return await UsuarioService.get(db_session, usuario_id, include_deleted=True)


@router.post(
    "/",
    response_model=UsuarioResponseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un usuario",
    description="Solo con un rol inferior al de quien lo crea. Empieza con el plan free.",
    responses=error_responses(401, 403, 409, 422, 500),
)
async def create_usuario(
    data: UsuarioCreate,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.CREATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UsuarioResponseDetail:
    return await UsuarioService.create(db_session, data, current_user)


@router.patch(
    "/{usuario_id}",
    response_model=UsuarioResponseDetail,
    summary="Editar un usuario",
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
async def update_usuario(
    usuario_id: UUID,
    data: UsuarioUpdate,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UsuarioResponseDetail:
    return await UsuarioService.update(db_session, usuario_id, data, current_user)


@router.delete(
    "/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un usuario",
    description="Responde 409 si tiene pagos o tarjeta: en ese caso se le da de baja.",
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
async def delete_usuario(
    usuario_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.DELETE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await UsuarioService.delete(db_session, usuario_id, current_user)


@router.post(
    "/{usuario_id}/dar-de-baja",
    response_model=UsuarioResponseDetail,
    summary="Dar de baja un usuario",
    description="Le impide iniciar sesión, revoca sus sesiones y despublica su tarjeta.",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def dar_de_baja_usuario(
    usuario_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UsuarioResponseDetail:
    return await UsuarioService.dar_de_baja(db_session, usuario_id, current_user)


@router.post(
    "/{usuario_id}/reactivar",
    response_model=UsuarioResponseDetail,
    summary="Reactivar un usuario",
    description="Su tarjeta sigue despublicada hasta que la vuelva a publicar.",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def reactivar_usuario(
    usuario_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UsuarioResponseDetail:
    return await UsuarioService.reactivar(db_session, usuario_id, current_user)
