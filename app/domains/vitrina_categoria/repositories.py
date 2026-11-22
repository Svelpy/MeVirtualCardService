from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tarjeta.repositories import TarjetaScope, tarjeta_ids_in_scope
from app.domains.vitrina_categoria.models import VitrinaCategoria


class VitrinaCategoriaRepository:
    @staticmethod
    async def get_for_audit(
        db_session: AsyncSession, categoria_id: UUID, *, scope: TarjetaScope
    ) -> VitrinaCategoria | None:
        """Eliminada o no, con el alcance de su tarjeta (§24), aunque la tarjeta esté eliminada."""
        tarjeta_ids = tarjeta_ids_in_scope(scope, include_deleted=True)
        # vitrina.id = tarjeta.id
        query = select(VitrinaCategoria).where(
            VitrinaCategoria.id == categoria_id, VitrinaCategoria.vitrina_id.in_(tarjeta_ids)
        )
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def get_in_vitrina(db_session: AsyncSession, categoria_id: UUID, vitrina_id: UUID) -> VitrinaCategoria | None:
        """Una categoría no eliminada de esa vitrina."""
        query = select(VitrinaCategoria).where(
            VitrinaCategoria.id == categoria_id,
            VitrinaCategoria.vitrina_id == vitrina_id,
            VitrinaCategoria.is_deleted.is_(False),
        )
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def mark_deleted_by_vitrina(db_session: AsyncSession, vitrina_id: UUID, now: datetime, actor_id: UUID) -> None:
        """Cascada (§19): las categorías de la vitrina."""
        await db_session.execute(
            update(VitrinaCategoria)
            .where(VitrinaCategoria.vitrina_id == vitrina_id, VitrinaCategoria.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=now, deleted_by=actor_id, updated_at=now, updated_by=actor_id)
        )
