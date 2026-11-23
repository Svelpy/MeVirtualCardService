from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.vitrina_item.models import VitrinaItem
from app.domains.vitrina_item.repositories import VitrinaItemRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class VitrinaItemService:
    """Hija embebida: se escribe desde la vitrina y solo expone su auditoría (§23)."""

    @staticmethod
    async def audit(db_session: AsyncSession, item_id: UUID, actor: CurrentUser) -> VitrinaItem:
        model = await VitrinaItemRepository.get_for_audit(db_session, item_id, scope=tarjeta_scope_for(actor))
        if model is None:
            raise AppException("Item no encontrado.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return model
