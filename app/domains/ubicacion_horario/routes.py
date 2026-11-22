from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.ubicacion_horario.schemas import UbicacionHorarioResponseAudit
from app.domains.ubicacion_horario.services import UbicacionHorarioService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Hija embebida: se crea, edita y elimina desde su padre; aquí solo su auditoría.
router = APIRouter(prefix="/ubicacion-horarios", tags=["Horarios de ubicación"])


@router.get(
    "/{horario_id}/audit",
    response_model=UbicacionHorarioResponseAudit,
    summary="Auditar un horario de ubicación",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_ubicacion_horario(
    horario_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.UBICACION_HORARIO, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UbicacionHorarioResponseAudit:
    return await UbicacionHorarioService.audit(db_session, horario_id, current_user)
