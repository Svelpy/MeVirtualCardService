from datetime import datetime, timedelta
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.security import hash_password
from app.domains.auth.repositories import (
    AuthSessionRepository,
    EmailVerificationTokenRepository,
    PasswordResetTokenRepository,
)
from app.domains.auth.schemas import CurrentUser
from app.domains.pago.repositories import PagoRepository
from app.domains.plan.services import PlanService
from app.domains.tarjeta.repositories import TarjetaRepository
from app.domains.tarjeta.schemas import UsuarioResponseMe
from app.domains.usuario.models import Usuario
from app.domains.usuario.repositories import UsuarioRepository
from app.domains.usuario.schemas import (
    UsuarioCreate,
    UsuarioResponseDetail,
    UsuarioResponseItemList,
    UsuarioUpdate,
    UsuarioUpdateMe,
)
from app.shared.enums import Role
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse
from app.shared.services.permissions import can_manage_role


def _ensure_can_manage(actor: CurrentUser, target_role: Role) -> None:
    """Jerarquía (§24): solo sobre roles estrictamente inferiores al del actor."""
    if not can_manage_role(actor.role, target_role):
        raise AppException(
            "No puedes gestionar usuarios con un rol igual o superior al tuyo.",
            status.HTTP_403_FORBIDDEN,
            ErrorCode.PERMISSION_DENIED,
        )


def _not_found() -> AppException:
    return AppException("Usuario no encontrado.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)


class UsuarioService:
    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int,
        per_page: int,
        rol: Role | None = None,
        plan_id: UUID | None = None,
        is_active: bool | None = None,
    ) -> PaginatedResponse[UsuarioResponseItemList]:
        usuarios, total = await UsuarioRepository.list(
            db_session, page=page, per_page=per_page, rol=rol, plan_id=plan_id, is_active=is_active
        )
        return PaginatedResponse[UsuarioResponseItemList].build(usuarios, total=total, page=page, per_page=per_page)

    @staticmethod
    async def get(db_session: AsyncSession, usuario_id: UUID, *, include_deleted: bool = False) -> Usuario:
        usuario = await UsuarioRepository.get(db_session, usuario_id, include_deleted=include_deleted, detail=True)
        if usuario is None:
            raise _not_found()
        return usuario

    @staticmethod
    async def add_new(
        db_session: AsyncSession,
        *,
        email: str,
        password: str,
        rol: Role,
        created_by: UUID | None,
    ) -> Usuario:
        """
        Agrega a la sesión un usuario nuevo, sin commit. Lo comparten el alta por
        un admin y el registro público: todo usuario empieza con el plan free y
        el email sin verificar.
        """
        await UsuarioService._ensure_email_available(db_session, email)
        plan = await PlanService.get_free(db_session)
        usuario = Usuario(
            email=email,
            password_hash=hash_password(password),
            rol=rol,
            plan_id=plan.id,
            plan_vence_at=utc_now() + timedelta(days=plan.duracion_dias),
            created_by=created_by,
        )
        db_session.add(usuario)
        await db_session.flush()  # asigna usuario.id
        return usuario

    @staticmethod
    async def create(db_session: AsyncSession, data: UsuarioCreate, actor: CurrentUser) -> Usuario:
        _ensure_can_manage(actor, data.rol)
        usuario = await UsuarioService.add_new(
            db_session, email=data.email, password=data.password, rol=data.rol, created_by=actor.id
        )
        await db_session.commit()
        return await UsuarioService.get(db_session, usuario.id)

    @staticmethod
    async def update(db_session: AsyncSession, usuario_id: UUID, data: UsuarioUpdate, actor: CurrentUser) -> Usuario:
        usuario = await UsuarioService.get(db_session, usuario_id)
        # Se valida el rol actual y el resultante: nadie sube a otro a su nivel.
        _ensure_can_manage(actor, usuario.rol)
        changes = data.model_dump(exclude_unset=True)
        if "rol" in changes:
            _ensure_can_manage(actor, changes["rol"])
        await UsuarioService._apply_changes(db_session, usuario, changes, actor)
        return await UsuarioService.get(db_session, usuario_id)

    @staticmethod
    async def get_me(db_session: AsyncSession, actor: CurrentUser) -> UsuarioResponseMe:
        """
        /me (§24): el usuario autenticado, su plan y su tarjeta completa, como la
        ve su dueño (null si todavía no la creó). El id sale solo de actor.id.
        """
        usuario = await UsuarioService.get(db_session, actor.id)
        tarjeta = await TarjetaRepository.get_by_user(db_session, actor.id)
        detail = UsuarioResponseDetail.model_validate(usuario).model_dump()
        return UsuarioResponseMe.model_validate({**detail, "tarjeta": tarjeta}, from_attributes=True)

    @staticmethod
    async def update_me(db_session: AsyncSession, data: UsuarioUpdateMe, actor: CurrentUser) -> Usuario:
        usuario = await UsuarioService.get(db_session, actor.id)
        await UsuarioService._apply_changes(db_session, usuario, data.model_dump(exclude_unset=True), actor)
        return await UsuarioService.get(db_session, actor.id)

    @staticmethod
    async def delete(db_session: AsyncSession, usuario_id: UUID, actor: CurrentUser) -> None:
        usuario = await UsuarioService.get(db_session, usuario_id)
        _ensure_can_manage(actor, usuario.rol)

        # Referencias que bloquean (§19): el kardex de pagos y su tarjeta.
        if await PagoRepository.exists_for_user(db_session, usuario_id):
            raise AppException(
                "El usuario tiene pagos registrados: dalo de baja en lugar de eliminarlo.",
                status.HTTP_409_CONFLICT,
                ErrorCode.CONFLICT,
            )
        if await TarjetaRepository.exists_for_user(db_session, usuario_id):
            raise AppException(
                "El usuario tiene una tarjeta: dalo de baja en lugar de eliminarlo.",
                status.HTTP_409_CONFLICT,
                ErrorCode.CONFLICT,
            )

        now = utc_now()
        await AuthSessionRepository.revoke_all_for_user(db_session, usuario_id, now, "user_deleted")
        await UsuarioService._revoke_pending_tokens(db_session, usuario_id, now)
        UsuarioRepository.mark_deleted(usuario, now, actor.id)
        await db_session.commit()

    @staticmethod
    async def dar_de_baja(db_session: AsyncSession, usuario_id: UUID, actor: CurrentUser) -> Usuario:
        """Impide el login y el refresh, revoca sus sesiones y despublica su tarjeta."""
        usuario = await UsuarioService.get(db_session, usuario_id)
        _ensure_can_manage(actor, usuario.rol)
        if usuario.is_active:
            now = utc_now()
            usuario.is_active = False
            usuario.updated_at = now
            usuario.updated_by = actor.id
            await AuthSessionRepository.revoke_all_for_user(db_session, usuario_id, now, "user_deactivated")
            await TarjetaRepository.unpublish_for_user(db_session, usuario_id, now, actor.id)
            await db_session.commit()
        return await UsuarioService.get(db_session, usuario_id)

    @staticmethod
    async def reactivar(db_session: AsyncSession, usuario_id: UUID, actor: CurrentUser) -> Usuario:
        """La tarjeta sigue despublicada hasta que su dueño la vuelva a publicar."""
        usuario = await UsuarioService.get(db_session, usuario_id)
        _ensure_can_manage(actor, usuario.rol)
        if not usuario.is_active:
            usuario.is_active = True
            usuario.updated_at = utc_now()
            usuario.updated_by = actor.id
            await db_session.commit()
        return await UsuarioService.get(db_session, usuario_id)

    @staticmethod
    async def _apply_changes(
        db_session: AsyncSession,
        usuario: Usuario,
        changes: dict[str, object],
        actor: CurrentUser,
    ) -> None:
        now = utc_now()
        email = changes.pop("email", None)
        changed = False
        if email is not None and email != usuario.email:
            await UsuarioService._ensure_email_available(db_session, email)
            # El email nuevo no está verificado, y los enlaces enviados al
            # anterior (verificación y recuperación) dejan de servir.
            usuario.email = email
            usuario.email_verified_at = None
            await UsuarioService._revoke_pending_tokens(db_session, usuario.id, now)
            changed = True
        for field, value in changes.items():
            if getattr(usuario, field) != value:
                setattr(usuario, field, value)
                changed = True
        if changed:
            usuario.updated_at = now
            usuario.updated_by = actor.id
            await db_session.commit()

    @staticmethod
    async def _ensure_email_available(db_session: AsyncSession, email: str) -> None:
        if await UsuarioRepository.get_by_email(db_session, email) is not None:
            raise AppException(
                "Ya existe un usuario con ese email.",
                status.HTTP_409_CONFLICT,
                ErrorCode.CONFLICT,
                details={"email": "Ya está registrado."},
            )

    @staticmethod
    async def _revoke_pending_tokens(db_session: AsyncSession, usuario_id: UUID, now: datetime) -> None:
        await EmailVerificationTokenRepository.revoke_pending_for_user(db_session, usuario_id, now)
        await PasswordResetTokenRepository.revoke_pending_for_user(db_session, usuario_id, now)
