from collections.abc import Sequence
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.domains.auth.schemas import CurrentUser
from app.domains.tarjeta.services import tarjeta_scope_for
from app.domains.vitrina.models import Vitrina
from app.domains.vitrina.repositories import VitrinaRepository
from app.domains.vitrina.schemas import VitrinaUpdateNested
from app.domains.vitrina_categoria.models import VitrinaCategoria
from app.domains.vitrina_item.repositories import VitrinaItemRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.services.nested_sync import apply_sync


class VitrinaService:
    @staticmethod
    async def get(
        db_session: AsyncSession,
        vitrina_id: UUID,
        actor: CurrentUser,
        *,
        include_deleted: bool = False,
    ) -> Vitrina:
        vitrina = await VitrinaRepository.get(
            db_session, vitrina_id, scope=tarjeta_scope_for(actor), include_deleted=include_deleted, detail=True
        )
        if vitrina is None:
            raise AppException("Vitrina no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return vitrina

    @staticmethod
    async def update(
        db_session: AsyncSession,
        vitrina_id: UUID,
        data: VitrinaUpdateNested,
        actor: CurrentUser,
    ) -> Vitrina:
        """Sus campos y sus categorías (estado final). Una categoría con items no se elimina: 409."""
        vitrina = await VitrinaService.get(db_session, vitrina_id, actor)
        changes = {
            field: value
            for field, value in data.model_dump(exclude_unset=True, exclude={"categorias"}).items()
            if getattr(vitrina, field) != value
        }
        now = utc_now()
        for field, value in changes.items():
            setattr(vitrina, field, value)

        if data.categorias is not None:

            async def ensure_unused(categorias: Sequence[VitrinaCategoria]) -> None:
                if await VitrinaItemRepository.exists_for_categorias(db_session, [c.id for c in categorias]):
                    raise AppException(
                        "Hay categorías con items: muévelos o elimínalos antes.",
                        status.HTTP_409_CONFLICT,
                        ErrorCode.CONFLICT,
                        details={"categorias": sorted(str(c.id) for c in categorias)},
                    )

            await apply_sync(
                db_session,
                field="categorias",
                existing=vitrina.categorias,
                items=data.categorias,
                build=lambda item: VitrinaCategoria(
                    vitrina_id=vitrina.id, **item.model_dump(exclude={"id"}), created_by=actor.id
                ),
                now=now,
                actor_id=actor.id,
                before_delete=ensure_unused,
            )

        if changes or data.categorias is not None:
            vitrina.updated_at = now
            vitrina.updated_by = actor.id
            await db_session.commit()
        return await VitrinaService.get(db_session, vitrina_id, actor)
