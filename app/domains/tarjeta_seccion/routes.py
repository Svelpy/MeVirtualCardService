from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta_seccion.schemas import TarjetaSeccionResponseAudit
from app.domains.tarjeta_seccion.services import TarjetaSeccionService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Hija embebida: se crea, edita y elimina desde su padre; aquí solo su auditoría.
router = APIRouter(prefix="/tarjeta-secciones", tags=["Secciones de tarjeta"])


@router.get(
    "/{seccion_id}/audit",
    response_model=TarjetaSeccionResponseAudit,
    summary="Auditar una sección de tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_tarjeta_seccion(
    seccion_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_SECCION, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaSeccionResponseAudit:
    return await TarjetaSeccionService.audit(db_session, seccion_id, current_user)
