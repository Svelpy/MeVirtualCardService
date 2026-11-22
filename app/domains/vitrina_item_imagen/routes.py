from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.vitrina_item_imagen.schemas import VitrinaItemImagenResponseAudit
from app.domains.vitrina_item_imagen.services import VitrinaItemImagenService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Hija embebida: se crea, edita y elimina desde su padre; aquí solo su auditoría.
router = APIRouter(prefix="/vitrina-item-imagenes", tags=["Imágenes de items de vitrina"])


@router.get(
    "/{imagen_id}/audit",
    response_model=VitrinaItemImagenResponseAudit,
    summary="Auditar una imagen de item de vitrina",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_vitrina_item_imagen(
    imagen_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA_ITEM_IMAGEN, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> VitrinaItemImagenResponseAudit:
    return await VitrinaItemImagenService.audit(db_session, imagen_id, current_user)
