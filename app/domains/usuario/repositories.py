from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Usuario.plan se resuelve por nombre al configurar los mappers: su model tiene que estar cargado.
import app.domains.plan.models  # noqa: F401
from app.domains.usuario.models import Usuario
from app.shared.enums import Role


class UsuarioRepository:
    """Sin alcance: todo rol con acceso al módulo ve todos los usuarios (§24)."""

    @staticmethod
    async def get(
        db_session: AsyncSession,
        usuario_id: UUID,
        *,
        include_deleted: bool = False,
        detail: bool = False,
        for_update: bool = False,
    ) -> Usuario | None:
        query = select(Usuario).where(Usuario.id == usuario_id)
        if not include_deleted:
            query = query.where(Usuario.is_deleted.is_(False))
        if detail:
            query = query.options(selectinload(Usuario.plan))
        if for_update:
            query = query.with_for_update()
        # Recarga desde la base aunque ya esté en la sesión (respuesta después de un commit).
        query = query.execution_options(populate_existing=True)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def get_by_email(db_session: AsyncSession, email: str) -> Usuario | None:
        """Login y unicidad: entre todos los usuarios no eliminados."""
        query = select(Usuario).where(Usuario.email == email, Usuario.is_deleted.is_(False))
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int,
        per_page: int,
        rol: Role | None,
        plan_id: UUID | None,
        is_active: bool | None,
    ) -> tuple[Sequence[Usuario], int]:
        conditions = [Usuario.is_deleted.is_(False)]
        if rol is not None:
            conditions.append(Usuario.rol == rol)
        if plan_id is not None:
            conditions.append(Usuario.plan_id == plan_id)
        if is_active is not None:
            conditions.append(Usuario.is_active.is_(is_active))
        total = (await db_session.execute(select(func.count()).select_from(Usuario).where(*conditions))).scalar_one()
        query = (
            select(Usuario)
            .where(*conditions)
            .options(selectinload(Usuario.plan))
            .order_by(Usuario.created_at.desc(), Usuario.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return (await db_session.execute(query)).scalars().all(), total

    @staticmethod
    def mark_deleted(usuario: Usuario, now: datetime, actor_id: UUID) -> None:
        usuario.is_deleted = True
        usuario.deleted_at = now
        usuario.deleted_by = actor_id
        usuario.updated_at = now
        usuario.updated_by = actor_id
