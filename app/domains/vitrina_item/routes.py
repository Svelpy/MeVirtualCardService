from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.vitrina_item.schemas import (
    VitrinaItemCreateNested,
    VitrinaItemPublic,
    VitrinaItemResponseAudit,
    VitrinaItemResponseDetail,
    VitrinaItemResponseItemList,
    VitrinaItemUpdateNested,
)
from app.domains.vitrina_item.services import VitrinaItemService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses
from app.shared.schemas.pagination import PaginatedResponse


# Hija paginada de la vitrina, con sus imágenes como hijas embebidas.
router = APIRouter(prefix="/vitrina-items", tags=["Items de vitrina"])


# Antes de /{item_id}, para que "public" no se lea como un id.
@router.get(
    "/public",
    response_model=PaginatedResponse[VitrinaItemPublic],
    summary="Listar los items de una vitrina publicada",
    description=(
        "Sin login. Solo los items visibles, sin los de categorías ocultas, de una tarjeta publicada con "
        "su dueño activo y el plan vigente (404 si no)."
    ),
    responses=error_responses(404, 422, 500),
)
async def list_public_vitrina_items(
    db_session: Annotated[AsyncSession, Depends(get_db)],
    vitrina_id: Annotated[UUID, Query()],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    categoria_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedResponse[VitrinaItemPublic]:
    return await VitrinaItemService.list_public(
        db_session, vitrina_id=vitrina_id, page=page, per_page=per_page, categoria_id=categoria_id
    )


@router.get(
    "/",
    response_model=PaginatedResponse[VitrinaItemResponseItemList],
    summary="Listar items de vitrina",
    description="Ordenados por orden. Un usuario solo ve los de su tarjeta.",
    responses=error_responses(401, 403, 422, 500),
)
async def list_vitrina_items(
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA_ITEM, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    vitrina_id: Annotated[UUID | None, Query()] = None,
    categoria_id: Annotated[UUID | None, Query()] = None,
    is_visible: Annotated[bool | None, Query()] = None,
) -> PaginatedResponse[VitrinaItemResponseItemList]:
    return await VitrinaItemService.list(
        db_session,
        current_user,
        page=page,
        per_page=per_page,
        vitrina_id=vitrina_id,
        categoria_id=categoria_id,
        is_visible=is_visible,
    )


@router.get(
    "/{item_id}",
    response_model=VitrinaItemResponseDetail,
    summary="Obtener un item de vitrina",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def get_vitrina_item(
    item_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA_ITEM, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> VitrinaItemResponseDetail:
    return await VitrinaItemService.get(db_session, item_id, current_user)


@router.get(
    "/{item_id}/audit",
    response_model=VitrinaItemResponseAudit,
    summary="Auditar un item de vitrina",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_vitrina_item(
    item_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA_ITEM, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> VitrinaItemResponseAudit:
    return await VitrinaItemService.get(db_session, item_id, current_user, include_deleted=True)


@router.post(
    "/",
    response_model=VitrinaItemResponseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un item de vitrina",
    responses=error_responses(401, 403, 422, 500),
)
async def create_vitrina_item(
    data: VitrinaItemCreateNested,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA_ITEM, Action.CREATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VitrinaItemResponseDetail:
    return await VitrinaItemService.create(db_session, data, current_user, settings)


@router.patch(
    "/{item_id}",
    response_model=VitrinaItemResponseDetail,
    summary="Editar un item de vitrina",
    description="imagenes es el estado final: ausente o null no se toca, [] las elimina.",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def update_vitrina_item(
    item_id: UUID,
    data: VitrinaItemUpdateNested,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA_ITEM, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VitrinaItemResponseDetail:
    return await VitrinaItemService.update(db_session, item_id, data, current_user, settings)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un item de vitrina",
    description="Elimina también sus imágenes.",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def delete_vitrina_item(
    item_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA_ITEM, Action.DELETE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await VitrinaItemService.delete(db_session, item_id, current_user)
