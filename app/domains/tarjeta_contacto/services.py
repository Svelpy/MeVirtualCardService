from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.tarjeta_contacto.models import TarjetaContacto
from app.domains.tarjeta_contacto.repositories import TarjetaContactoRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class TarjetaContactoService:
    """Hija embebida: se escribe desde su padre y solo expone su auditoría (§23)."""

    @staticmethod
    async def audit(db_session: AsyncSession, contacto_id: UUID, actor: CurrentUser) -> TarjetaContacto:
        model = await TarjetaContactoRepository.get_for_audit(db_session, contacto_id, scope=tarjeta_scope_for(actor))
        if model is None:
            raise AppException("Contacto no encontrado.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return model
