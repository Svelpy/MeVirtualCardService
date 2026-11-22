from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.models import AuthSession, EmailVerificationToken, PasswordResetToken


class AuthSessionRepository:
    @staticmethod
    async def get_by_token_hash(db_session: AsyncSession, refresh_token_hash: str) -> AuthSession | None:
        """Bloquea la fila: dos refresh simultáneos con el mismo token no rotan dos veces."""
        query = (
            select(AuthSession)
            .where(AuthSession.refresh_token_hash == refresh_token_hash, AuthSession.is_deleted.is_(False))
            .with_for_update()
        )
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def revoke_all_for_user(db_session: AsyncSession, user_id: UUID, now: datetime, reason: str) -> None:
        """Revoca las sesiones activas del usuario: su refresh token deja de servir."""
        await db_session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now, revocation_reason=reason, updated_at=now)
        )

    @staticmethod
    async def revoke_family(db_session: AsyncSession, family_id: UUID, now: datetime, reason: str) -> None:
        """Revoca todas las sesiones que nacieron del mismo login."""
        await db_session.execute(
            update(AuthSession)
            .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now, revocation_reason=reason, updated_at=now)
        )


type OneTimeTokenModel = type[PasswordResetToken] | type[EmailVerificationToken]


async def _get_token_by_hash[T: (PasswordResetToken, EmailVerificationToken)](
    db_session: AsyncSession, model: type[T], token_hash: str
) -> T | None:
    query = select(model).where(model.token_hash == token_hash, model.is_deleted.is_(False)).with_for_update()
    return (await db_session.execute(query)).scalars().first()


async def _revoke_pending_tokens(db_session: AsyncSession, model: OneTimeTokenModel, user_id: UUID, now: datetime) -> None:
    await db_session.execute(
        update(model)
        .where(
            model.user_id == user_id,
            model.used_at.is_(None),
            model.revoked_at.is_(None),
            model.is_deleted.is_(False),
        )
        .values(revoked_at=now, updated_at=now)
    )


class PasswordResetTokenRepository:
    @staticmethod
    async def get_by_token_hash(db_session: AsyncSession, token_hash: str) -> PasswordResetToken | None:
        return await _get_token_by_hash(db_session, PasswordResetToken, token_hash)

    @staticmethod
    async def revoke_pending_for_user(db_session: AsyncSession, user_id: UUID, now: datetime) -> None:
        await _revoke_pending_tokens(db_session, PasswordResetToken, user_id, now)


class EmailVerificationTokenRepository:
    @staticmethod
    async def get_by_token_hash(db_session: AsyncSession, token_hash: str) -> EmailVerificationToken | None:
        return await _get_token_by_hash(db_session, EmailVerificationToken, token_hash)

    @staticmethod
    async def revoke_pending_for_user(db_session: AsyncSession, user_id: UUID, now: datetime) -> None:
        await _revoke_pending_tokens(db_session, EmailVerificationToken, user_id, now)
