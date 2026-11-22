from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.tarjeta_ubicacion.models import TarjetaUbicacion
from app.domains.tarjeta_ubicacion.repositories import TarjetaUbicacionRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class TarjetaUbicacionService:
    """Hija embebida: se escribe desde su padre y solo expone su auditoría (§23)."""

    @staticmethod
    async def audit(db_session: AsyncSession, ubicacion_id: UUID, actor: CurrentUser) -> TarjetaUbicacion:
        model = await TarjetaUbicacionRepository.get_for_audit(db_session, ubicacion_id, scope=tarjeta_scope_for(actor))
        if model is None:
            raise AppException("Ubicación no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return model
