from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.plan.models import Plan


class PlanRepository:
    """Filas fijas: sin alcance, porque todo rol con acceso ve todos los planes."""

    @staticmethod
    async def get(db_session: AsyncSession, plan_id: UUID, *, include_deleted: bool = False) -> Plan | None:
        query = select(Plan).where(Plan.id == plan_id)
        if not include_deleted:
            query = query.where(Plan.is_deleted.is_(False))
        # Recarga desde la base aunque el plan ya esté en la sesión: después de
        # un commit, la respuesta muestra lo guardado (90.50, no 90.5).
        query = query.execution_options(populate_existing=True)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def get_by_codigo(db_session: AsyncSession, codigo: str) -> Plan | None:
        query = select(Plan).where(Plan.codigo == codigo, Plan.is_deleted.is_(False))
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int,
        per_page: int,
        is_visible: bool | None,
    ) -> tuple[Sequence[Plan], int]:
        conditions = [Plan.is_deleted.is_(False)]
        if is_visible is not None:
            conditions.append(Plan.is_visible.is_(is_visible))
        total = (await db_session.execute(select(func.count()).select_from(Plan).where(*conditions))).scalar_one()
        query = (
            select(Plan)
            .where(*conditions)
            .order_by(Plan.created_at.desc(), Plan.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return (await db_session.execute(query)).scalars().all(), total

    @staticmethod
    async def list_visible(db_session: AsyncSession) -> Sequence[Plan]:
        """Página de precios: del más barato al más caro."""
        query = (
            select(Plan)
            .where(Plan.is_deleted.is_(False), Plan.is_visible.is_(True))
            .order_by(Plan.precio, Plan.duracion_dias)
        )
        return (await db_session.execute(query)).scalars().all()
