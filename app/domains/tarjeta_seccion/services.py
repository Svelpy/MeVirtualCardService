from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.tarjeta_seccion.models import TarjetaSeccion
from app.domains.tarjeta_seccion.repositories import TarjetaSeccionRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class TarjetaSeccionService:
    """Hija embebida: se escribe desde su padre y solo expone su auditoría (§23)."""

    @staticmethod
    async def audit(db_session: AsyncSession, seccion_id: UUID, actor: CurrentUser) -> TarjetaSeccion:
        model = await TarjetaSeccionRepository.get_for_audit(db_session, seccion_id, scope=tarjeta_scope_for(actor))
        if model is None:
            raise AppException("Sección no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return model
