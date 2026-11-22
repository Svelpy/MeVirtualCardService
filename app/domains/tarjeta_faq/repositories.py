from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tarjeta.repositories import TarjetaScope, tarjeta_ids_in_scope
from app.domains.tarjeta_faq.models import TarjetaFaq


class TarjetaFaqRepository:
    @staticmethod
    async def get_for_audit(
        db_session: AsyncSession, faq_id: UUID, *, scope: TarjetaScope
    ) -> TarjetaFaq | None:
        """Eliminada o no, con el alcance de su tarjeta (§24), aunque la tarjeta esté eliminada."""
        tarjeta_ids = tarjeta_ids_in_scope(scope, include_deleted=True)
        query = select(TarjetaFaq).where(TarjetaFaq.id == faq_id, TarjetaFaq.tarjeta_id.in_(tarjeta_ids))
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def mark_deleted_by_tarjeta(db_session: AsyncSession, tarjeta_id: UUID, now: datetime, actor_id: UUID) -> None:
        """Cascada (§19): las preguntas frecuentes de la tarjeta."""
        await db_session.execute(
            update(TarjetaFaq)
            .where(TarjetaFaq.tarjeta_id == tarjeta_id, TarjetaFaq.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=now, deleted_by=actor_id, updated_at=now, updated_by=actor_id)
        )
