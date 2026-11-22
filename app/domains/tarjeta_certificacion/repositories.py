from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tarjeta.repositories import TarjetaScope, tarjeta_ids_in_scope
from app.domains.tarjeta_certificacion.models import TarjetaCertificacion


class TarjetaCertificacionRepository:
    @staticmethod
    async def get_for_audit(
        db_session: AsyncSession, certificacion_id: UUID, *, scope: TarjetaScope
    ) -> TarjetaCertificacion | None:
        """Eliminada o no, con el alcance de su tarjeta (§24), aunque la tarjeta esté eliminada."""
        tarjeta_ids = tarjeta_ids_in_scope(scope, include_deleted=True)
        query = select(TarjetaCertificacion).where(TarjetaCertificacion.id == certificacion_id, TarjetaCertificacion.tarjeta_id.in_(tarjeta_ids))
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def mark_deleted_by_tarjeta(db_session: AsyncSession, tarjeta_id: UUID, now: datetime, actor_id: UUID) -> None:
        """Cascada (§19): las certificaciones de la tarjeta."""
        await db_session.execute(
            update(TarjetaCertificacion)
            .where(TarjetaCertificacion.tarjeta_id == tarjeta_id, TarjetaCertificacion.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=now, deleted_by=actor_id, updated_at=now, updated_by=actor_id)
        )
