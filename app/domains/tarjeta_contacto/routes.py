from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta_contacto.schemas import TarjetaContactoResponseAudit
from app.domains.tarjeta_contacto.services import TarjetaContactoService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Hija embebida: se crea, edita y elimina desde su padre; aquí solo su auditoría.
router = APIRouter(prefix="/tarjeta-contactos", tags=["Contactos de tarjeta"])


@router.get(
    "/{contacto_id}/audit",
    response_model=TarjetaContactoResponseAudit,
    summary="Auditar un contacto de tarjeta",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_tarjeta_contacto(
    contacto_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_CONTACTO, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaContactoResponseAudit:
    return await TarjetaContactoService.audit(db_session, contacto_id, current_user)
