from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.vitrina_categoria.models import VitrinaCategoria
from app.domains.vitrina_categoria.repositories import VitrinaCategoriaRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


class VitrinaCategoriaService:
    """Hija embebida: se escribe desde su padre y solo expone su auditoría (§23)."""

    @staticmethod
    async def audit(db_session: AsyncSession, categoria_id: UUID, actor: CurrentUser) -> VitrinaCategoria:
        model = await VitrinaCategoriaRepository.get_for_audit(db_session, categoria_id, scope=tarjeta_scope_for(actor))
        if model is None:
            raise AppException("Categoría no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return model
