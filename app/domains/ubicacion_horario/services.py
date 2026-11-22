from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.ubicacion_horario.models import UbicacionHorario
from app.domains.ubicacion_horario.repositories import UbicacionHorarioRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class UbicacionHorarioService:
    """Hija embebida: se escribe desde su padre y solo expone su auditoría (§23)."""

    @staticmethod
    async def audit(db_session: AsyncSession, horario_id: UUID, actor: CurrentUser) -> UbicacionHorario:
        model = await UbicacionHorarioRepository.get_for_audit(db_session, horario_id, scope=tarjeta_scope_for(actor))
        if model is None:
            raise AppException("Horario no encontrado.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return model
