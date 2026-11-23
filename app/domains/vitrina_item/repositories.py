from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tarjeta.repositories import TarjetaScope, tarjeta_ids_in_scope
from app.domains.vitrina_item.models import VitrinaItem


class VitrinaItemRepository:
    """Hija embebida de la vitrina; aplica el alcance de su tarjeta (vitrina.id = tarjeta.id)."""

    @staticmethod
    async def get_for_audit(db_session: AsyncSession, item_id: UUID, *, scope: TarjetaScope) -> VitrinaItem | None:
        """Eliminado o no, con el alcance de su tarjeta (§24), aunque la tarjeta esté eliminada."""
        tarjeta_ids = tarjeta_ids_in_scope(scope, include_deleted=True)
        query = select(VitrinaItem).where(VitrinaItem.id == item_id, VitrinaItem.vitrina_id.in_(tarjeta_ids))
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def exists_for_categorias(db_session: AsyncSession, categoria_ids: Collection[UUID]) -> bool:
        """Integridad (§19): items no eliminados que usan alguna de esas categorías, sin alcance."""
        query = select(
            exists().where(VitrinaItem.categoria_id.in_(categoria_ids), VitrinaItem.is_deleted.is_(False))
        )
        return bool((await db_session.execute(query)).scalar())

    @staticmethod
    async def mark_deleted_by_vitrina(db_session: AsyncSession, vitrina_id: UUID, now: datetime, actor_id: UUID) -> None:
        """Cascada (§19): los items de la vitrina; sus imágenes las marca VitrinaItemImagenRepository."""
        await db_session.execute(
            update(VitrinaItem)
            .where(VitrinaItem.vitrina_id == vitrina_id, VitrinaItem.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=now, deleted_by=actor_id, updated_at=now, updated_by=actor_id)
        )
