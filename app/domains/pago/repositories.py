from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

# Pago.user y Pago.plan se resuelven por nombre al configurar los mappers.
import app.domains.plan.models  # noqa: F401
import app.domains.usuario.models  # noqa: F401
from app.domains.pago.models import Pago


class PagoRepository:
    """
    Registro (kardex): sin soft delete ni alcance. Solo los admins lo usan, y
    todos ven todas las filas (§24).
    """

    @staticmethod
    async def get(db_session: AsyncSession, pago_id: UUID, *, detail: bool = False) -> Pago | None:
        query = select(Pago).where(Pago.id == pago_id)
        if detail:
            query = query.options(selectinload(Pago.user), selectinload(Pago.plan))
        query = query.execution_options(populate_existing=True)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def get_by_idempotency_key(db_session: AsyncSession, idempotency_key: str) -> Pago | None:
        query = select(Pago).where(Pago.idempotency_key == idempotency_key)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def is_reversed(db_session: AsyncSession, pago_id: UUID) -> bool:
        query = select(exists().where(Pago.reverses_id == pago_id))
        return bool((await db_session.execute(query)).scalar())

    @staticmethod
    async def latest_effective_for_user(db_session: AsyncSession, user_id: UUID) -> Pago | None:
        """Último pago del usuario que no es un reverso ni está anulado."""
        reverso = aliased(Pago)
        query = (
            select(Pago)
            .where(
                Pago.user_id == user_id,
                Pago.reverses_id.is_(None),
                ~exists().where(reverso.reverses_id == Pago.id),
            )
            .order_by(Pago.created_at.desc(), Pago.id)
            .limit(1)
        )
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def exists_for_user(db_session: AsyncSession, user_id: UUID) -> bool:
        """Kardex: todo pago cuenta como referencia, también los anulados (§19)."""
        return bool((await db_session.execute(select(exists().where(Pago.user_id == user_id)))).scalar())

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int,
        per_page: int,
        user_id: UUID | None,
        plan_id: UUID | None,
    ) -> tuple[Sequence[Pago], int]:
        conditions = []
        if user_id is not None:
            conditions.append(Pago.user_id == user_id)
        if plan_id is not None:
            conditions.append(Pago.plan_id == plan_id)
        total = (await db_session.execute(select(func.count()).select_from(Pago).where(*conditions))).scalar_one()
        query = (
            select(Pago)
            .where(*conditions)
            .options(selectinload(Pago.user), selectinload(Pago.plan))
            .order_by(Pago.created_at.desc(), Pago.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return (await db_session.execute(query)).scalars().all(), total
