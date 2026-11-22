from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.vitrina_item_imagen.models import VitrinaItemImagen
from app.domains.vitrina_item_imagen.repositories import VitrinaItemImagenRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class VitrinaItemImagenService:
    """Hija embebida: se escribe desde su padre y solo expone su auditoría (§23)."""

    @staticmethod
    async def audit(db_session: AsyncSession, imagen_id: UUID, actor: CurrentUser) -> VitrinaItemImagen:
        model = await VitrinaItemImagenRepository.get_for_audit(db_session, imagen_id, scope=tarjeta_scope_for(actor))
        if model is None:
            raise AppException("Imagen no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return model
