from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta_theme.schemas import (
    TarjetaThemeAplicarPreset,
    TarjetaThemeResponse,
    TarjetaThemeResponseAudit,
    TarjetaThemeUpdate,
)
from app.domains.tarjeta_theme.services import TarjetaThemeService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Extensión 1:1 de la tarjeta: su id es el de la tarjeta. Se crea y se elimina con ella.
router = APIRouter(prefix="/tarjeta-themes", tags=["Themes de tarjeta"])


@router.get(
    "/{theme_id}",
    response_model=TarjetaThemeResponse,
    summary="Obtener el theme de una tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def get_tarjeta_theme(
    theme_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_THEME, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaThemeResponse:
    return await TarjetaThemeService.get(db_session, theme_id, current_user)


@router.get(
    "/{theme_id}/audit",
    response_model=TarjetaThemeResponseAudit,
    summary="Auditar el theme de una tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_tarjeta_theme(
    theme_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_THEME, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaThemeResponseAudit:
    return await TarjetaThemeService.get(db_session, theme_id, current_user, include_deleted=True)


@router.patch(
    "/{theme_id}",
    response_model=TarjetaThemeResponse,
    summary="Editar el theme de una tarjeta",
    description=(
        "Un campo que no se envía no cambia. Cambiar a mano un valor del preset (los color_*, "
        "overlay_opacidad, icono_forma o fab_posicion) deja el theme como personalizado (preset null); "
        "cambiar la tipografía no. Para volver a un preset: POST /{id}/aplicar-preset."
    ),
    responses=error_responses(401, 403, 404, 422, 500),
)
async def update_tarjeta_theme(
    theme_id: UUID,
    data: TarjetaThemeUpdate,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_THEME, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaThemeResponse:
    return await TarjetaThemeService.update(db_session, theme_id, data, current_user)


@router.post(
    "/{theme_id}/aplicar-preset",
    response_model=TarjetaThemeResponse,
    summary="Aplicar un preset al theme",
    description=(
        "Copia los valores del preset: los 20 colores, overlay_opacidad, icono_forma y fab_posicion, y "
        "deja preset con su nombre. La tipografía no cambia. Sirve también para volver a un preset "
        "después de personalizar el theme."
    ),
    responses=error_responses(401, 403, 404, 422, 500),
)
async def aplicar_preset_tarjeta_theme(
    theme_id: UUID,
    data: TarjetaThemeAplicarPreset,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_THEME, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaThemeResponse:
    return await TarjetaThemeService.aplicar_preset(db_session, theme_id, data, current_user)
