from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.tarjeta.repositories import TarjetaScope, tarjeta_ids_in_scope
from app.domains.vitrina.models import Vitrina
from app.domains.vitrina_categoria.models import VitrinaCategoria
from app.domains.vitrina_item.models import VitrinaItem
from app.domains.vitrina_item_imagen.models import VitrinaItemImagen


class VitrinaRepository:
    @staticmethod
    async def get(
        db_session: AsyncSession,
        vitrina_id: UUID,
        *,
        scope: TarjetaScope,
        include_deleted: bool = False,
        detail: bool = False,
    ) -> Vitrina | None:
        """Extensión 1:1: aplica el alcance de su tarjeta (vitrina_id = tarjeta.id)."""
        tarjeta_ids = tarjeta_ids_in_scope(scope, include_deleted=include_deleted)
        query = select(Vitrina).where(Vitrina.id == vitrina_id, Vitrina.id.in_(tarjeta_ids))
        if not include_deleted:
            query = query.where(Vitrina.is_deleted.is_(False))
        if detail:
            query = query.options(
                selectinload(Vitrina.categorias.and_(VitrinaCategoria.is_deleted.is_(False))),
                selectinload(Vitrina.items.and_(VitrinaItem.is_deleted.is_(False))).options(
                    selectinload(VitrinaItem.categoria),
                    selectinload(VitrinaItem.imagenes.and_(VitrinaItemImagen.is_deleted.is_(False))),
                ),
            )
        query = query.execution_options(populate_existing=True)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def mark_deleted_by_tarjeta(db_session: AsyncSession, tarjeta_id: UUID, now: datetime, actor_id: UUID) -> None:
        """Cascada (§19): la Extensión 1:1 cae con su tarjeta."""
        await db_session.execute(
            update(Vitrina)
            .where(Vitrina.id == tarjeta_id, Vitrina.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=now, deleted_by=actor_id, updated_at=now, updated_by=actor_id)
        )
