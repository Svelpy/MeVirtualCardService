from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.tarjeta.repositories import TarjetaScope, tarjeta_ids_in_scope
from app.domains.tarjeta_ubicacion.models import TarjetaUbicacion
from app.domains.ubicacion_horario.models import UbicacionHorario


class UbicacionHorarioRepository:
    @staticmethod
    async def get_for_audit(
        db_session: AsyncSession, horario_id: UUID, *, scope: TarjetaScope
    ) -> UbicacionHorario | None:
        """Eliminada o no, con el alcance de su tarjeta (§24), aunque la tarjeta esté eliminada."""
        tarjeta_ids = tarjeta_ids_in_scope(scope, include_deleted=True)
        ubicacion_ids = select(TarjetaUbicacion.id).where(TarjetaUbicacion.tarjeta_id.in_(tarjeta_ids))
        query = select(UbicacionHorario).where(
            UbicacionHorario.id == horario_id, UbicacionHorario.ubicacion_id.in_(ubicacion_ids)
        )
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def mark_deleted_by_tarjeta(db_session: AsyncSession, tarjeta_id: UUID, now: datetime, actor_id: UUID) -> None:
        """Cascada (§19): los horarios de todas las ubicaciones de la tarjeta."""
        ubicacion_ids = select(TarjetaUbicacion.id).where(TarjetaUbicacion.tarjeta_id == tarjeta_id)
        await db_session.execute(
            update(UbicacionHorario)
            .where(UbicacionHorario.ubicacion_id.in_(ubicacion_ids), UbicacionHorario.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=now, deleted_by=actor_id, updated_at=now, updated_by=actor_id)
        )
