from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.tarjeta_faq.models import TarjetaFaq
from app.domains.tarjeta_faq.repositories import TarjetaFaqRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class TarjetaFaqService:
    """Hija embebida: se escribe desde su padre y solo expone su auditoría (§23)."""

    @staticmethod
    async def audit(db_session: AsyncSession, faq_id: UUID, actor: CurrentUser) -> TarjetaFaq:
        model = await TarjetaFaqRepository.get_for_audit(db_session, faq_id, scope=tarjeta_scope_for(actor))
        if model is None:
            raise AppException("Pregunta frecuente no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return model
