from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta_faq.schemas import TarjetaFaqResponseAudit
from app.domains.tarjeta_faq.services import TarjetaFaqService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import error_responses


# Hija embebida: se crea, edita y elimina desde su padre; aquí solo su auditoría.
router = APIRouter(prefix="/tarjeta-faqs", tags=["Preguntas frecuentes de tarjeta"])


@router.get(
    "/{faq_id}/audit",
    response_model=TarjetaFaqResponseAudit,
    summary="Auditar una pregunta frecuente",
    responses=error_responses(401, 403, 404, 422, 500),
)
async def audit_tarjeta_faq(
    faq_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.TARJETA_FAQ, Action.AUDIT))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> TarjetaFaqResponseAudit:
    return await TarjetaFaqService.audit(db_session, faq_id, current_user)
