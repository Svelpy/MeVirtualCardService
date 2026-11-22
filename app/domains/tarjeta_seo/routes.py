from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta_seo.schemas import TarjetaSeoResponse, TarjetaSeoResponseAudit, TarjetaSeoUpdate
from app.domains.tarjeta_seo.services import TarjetaSeoService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Extensión 1:1 de la tarjeta: su id es el de la tarjeta. Se crea y se elimina con ella.
router = APIRouter(prefix="/tarjeta-seos", tags=["SEO de tarjeta"])


@router.get(
    "/{seo_id}",
    response_model=TarjetaSeoResponse,
    summary="Obtener el SEO de una tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def get_tarjeta_seo(
    seo_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_SEO, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaSeoResponse:
    return await TarjetaSeoService.get(db_session, seo_id, current_user)


@router.get(
    "/{seo_id}/audit",
    response_model=TarjetaSeoResponseAudit,
    summary="Auditar el SEO de una tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_tarjeta_seo(
    seo_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_SEO, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaSeoResponseAudit:
    return await TarjetaSeoService.get(db_session, seo_id, current_user, include_deleted=True)


@router.patch(
    "/{seo_id}",
    response_model=TarjetaSeoResponse,
    summary="Editar el SEO de una tarjeta",
    description="null en meta_title o meta_description los genera el frontend; og_image_url null usa la foto de perfil.",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def update_tarjeta_seo(
    seo_id: UUID,
    data: TarjetaSeoUpdate,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_SEO, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TarjetaSeoResponse:
    return await TarjetaSeoService.update(db_session, seo_id, data, current_user, settings)
