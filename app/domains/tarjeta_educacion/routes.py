from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta_educacion.schemas import TarjetaEducacionResponseAudit
from app.domains.tarjeta_educacion.services import TarjetaEducacionService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Hija embebida: se crea, edita y elimina desde su padre; aquí solo su auditoría.
router = APIRouter(prefix="/tarjeta-educaciones", tags=["Educación de tarjeta"])


@router.get(
    "/{educacion_id}/audit",
    response_model=TarjetaEducacionResponseAudit,
    summary="Auditar una educación de tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_tarjeta_educacion(
    educacion_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_EDUCACION, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaEducacionResponseAudit:
    return await TarjetaEducacionService.audit(db_session, educacion_id, current_user)
