from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.tarjeta_social.models import TarjetaSocial
from app.domains.tarjeta_social.repositories import TarjetaSocialRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class TarjetaSocialService:
    """Hija embebida: se escribe desde su padre y solo expone su auditoría (§23)."""

    @staticmethod
    async def audit(db_session: AsyncSession, red_id: UUID, actor: CurrentUser) -> TarjetaSocial:
        model = await TarjetaSocialRepository.get_for_audit(db_session, red_id, scope=tarjeta_scope_for(actor))
        if model is None:
            raise AppException("Red social no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return model
