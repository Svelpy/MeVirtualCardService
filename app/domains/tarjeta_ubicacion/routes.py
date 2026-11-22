from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta_ubicacion.schemas import TarjetaUbicacionResponseAudit
from app.domains.tarjeta_ubicacion.services import TarjetaUbicacionService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Hija embebida: se crea, edita y elimina desde su padre; aquí solo su auditoría.
router = APIRouter(prefix="/tarjeta-ubicaciones", tags=["Ubicaciones de tarjeta"])


@router.get(
    "/{ubicacion_id}/audit",
    response_model=TarjetaUbicacionResponseAudit,
    summary="Auditar una ubicación de tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_tarjeta_ubicacion(
    ubicacion_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_UBICACION, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaUbicacionResponseAudit:
    return await TarjetaUbicacionService.audit(db_session, ubicacion_id, current_user)
