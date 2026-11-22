from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta_certificacion.schemas import TarjetaCertificacionResponseAudit
from app.domains.tarjeta_certificacion.services import TarjetaCertificacionService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Hija embebida: se crea, edita y elimina desde su padre; aquí solo su auditoría.
router = APIRouter(prefix="/tarjeta-certificaciones", tags=["Certificaciones de tarjeta"])


@router.get(
    "/{certificacion_id}/audit",
    response_model=TarjetaCertificacionResponseAudit,
    summary="Auditar una certificación de tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_tarjeta_certificacion(
    certificacion_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_CERTIFICACION, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaCertificacionResponseAudit:
    return await TarjetaCertificacionService.audit(db_session, certificacion_id, current_user)
