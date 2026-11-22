from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.tarjeta_certificacion.models import TarjetaCertificacion
from app.domains.tarjeta_certificacion.repositories import TarjetaCertificacionRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class TarjetaCertificacionService:
    """Hija embebida: se escribe desde su padre y solo expone su auditoría (§23)."""

    @staticmethod
    async def audit(db_session: AsyncSession, certificacion_id: UUID, actor: CurrentUser) -> TarjetaCertificacion:
        model = await TarjetaCertificacionRepository.get_for_audit(db_session, certificacion_id, scope=tarjeta_scope_for(actor))
        if model is None:
            raise AppException("Certificación no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return model
