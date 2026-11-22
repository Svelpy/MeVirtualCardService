from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.vitrina_categoria.schemas import VitrinaCategoriaResponseAudit
from app.domains.vitrina_categoria.services import VitrinaCategoriaService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Hija embebida: se crea, edita y elimina desde su padre; aquí solo su auditoría.
router = APIRouter(prefix="/vitrina-categorias", tags=["Categorías de vitrina"])


@router.get(
    "/{categoria_id}/audit",
    response_model=VitrinaCategoriaResponseAudit,
    summary="Auditar una categoría de vitrina",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_vitrina_categoria(
    categoria_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.VITRINA_CATEGORIA, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> VitrinaCategoriaResponseAudit:
    return await VitrinaCategoriaService.audit(db_session, categoria_id, current_user)
