from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.vitrina_item.schemas import VitrinaItemResponseAudit
from app.domains.vitrina_item.services import VitrinaItemService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Hija embebida: se crea, edita y elimina desde su vitrina; aquí solo su auditoría.
router = APIRouter(prefix="/vitrina-items", tags=["Items de vitrina"])


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
    return await VitrinaItemService.audit(db_session, item_id, current_user)
