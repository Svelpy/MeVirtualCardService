from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.vitrina.schemas import VitrinaResponseAudit, VitrinaResponseDetail, VitrinaUpdateNested
from app.domains.vitrina.services import VitrinaService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Extensión 1:1 de la tarjeta: su id es el de la tarjeta. Se crea y se elimina
# con ella; sus categorías y sus items (con sus imágenes) se escriben aquí.
router = APIRouter(prefix="/vitrinas", tags=["Vitrinas"])


@router.get(
    "/{vitrina_id}",
    response_model=VitrinaResponseDetail,
    summary="Obtener la vitrina de una tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def get_vitrina(
    vitrina_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> VitrinaResponseDetail:
    return await VitrinaService.get(db_session, vitrina_id, current_user)


@router.get(
    "/{vitrina_id}/audit",
    response_model=VitrinaResponseAudit,
    summary="Auditar la vitrina de una tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_vitrina(
    vitrina_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> VitrinaResponseAudit:
    return await VitrinaService.get(db_session, vitrina_id, current_user, include_deleted=True)


@router.patch(
    "/{vitrina_id}",
    response_model=VitrinaResponseDetail,
    summary="Editar la vitrina de una tarjeta",
    description=(
        "categorias e items son el estado final: ausente o null no se toca, [] los elimina. Máximo "
        "25 items y 3 imágenes por item. Un item solo usa una categoría existente que se conserva (422). "
        "Una categoría que sigue con items no se puede eliminar (409)."
    ),
    responses=error_responses(401, 403, 404, 409, 422, 500),
)
async def update_vitrina(
    vitrina_id: UUID,
    data: VitrinaUpdateNested,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> VitrinaResponseDetail:
    return await VitrinaService.update(db_session, vitrina_id, data, current_user, settings)
