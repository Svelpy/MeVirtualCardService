from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tarjeta.repositories import TarjetaScope, tarjeta_ids_in_scope
from app.domains.tarjeta_theme.models import TarjetaTheme


class TarjetaThemeRepository:
    @staticmethod
    async def get(
        db_session: AsyncSession,
        theme_id: UUID,
        *,
        scope: TarjetaScope,
        include_deleted: bool = False,
    ) -> TarjetaTheme | None:
        """Extensión 1:1: aplica el alcance de su tarjeta (theme_id = tarjeta.id)."""
        tarjeta_ids = tarjeta_ids_in_scope(scope, include_deleted=include_deleted)
        query = select(TarjetaTheme).where(TarjetaTheme.id == theme_id, TarjetaTheme.id.in_(tarjeta_ids))
        if not include_deleted:
            query = query.where(TarjetaTheme.is_deleted.is_(False))
        query = query.execution_options(populate_existing=True)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def mark_deleted_by_tarjeta(db_session: AsyncSession, tarjeta_id: UUID, now: datetime, actor_id: UUID) -> None:
        """Cascada (§19): la Extensión 1:1 cae con su tarjeta."""
        await db_session.execute(
            update(TarjetaTheme)
            .where(TarjetaTheme.id == tarjeta_id, TarjetaTheme.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=now, deleted_by=actor_id, updated_at=now, updated_by=actor_id)
        )
