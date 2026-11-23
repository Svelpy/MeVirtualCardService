from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tarjeta.repositories import TarjetaScope, tarjeta_ids_in_scope
from app.domains.vitrina_item.models import VitrinaItem
from app.domains.vitrina_item_imagen.models import VitrinaItemImagen


class VitrinaItemImagenRepository:
    @staticmethod
    async def get_for_audit(
        db_session: AsyncSession, imagen_id: UUID, *, scope: TarjetaScope
    ) -> VitrinaItemImagen | None:
        """Eliminada o no, con el alcance de su tarjeta (§24), aunque la tarjeta esté eliminada."""
        tarjeta_ids = tarjeta_ids_in_scope(scope, include_deleted=True)
        item_ids = select(VitrinaItem.id).where(VitrinaItem.vitrina_id.in_(tarjeta_ids))
        query = select(VitrinaItemImagen).where(VitrinaItemImagen.id == imagen_id, VitrinaItemImagen.item_id.in_(item_ids))
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def mark_deleted_by_vitrina(db_session: AsyncSession, vitrina_id: UUID, now: datetime, actor_id: UUID) -> None:
        """Cascada (§19): las imágenes de todos los items de la vitrina."""
        item_ids = select(VitrinaItem.id).where(VitrinaItem.vitrina_id == vitrina_id)
        await db_session.execute(
            update(VitrinaItemImagen)
            .where(VitrinaItemImagen.item_id.in_(item_ids), VitrinaItemImagen.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=now, deleted_by=actor_id, updated_at=now, updated_by=actor_id)
        )
