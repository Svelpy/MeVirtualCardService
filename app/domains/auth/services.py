from datetime import datetime, timedelta
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_csrf_token,
    create_one_time_token,
    create_refresh_token,
    hash_one_time_token,
    hash_password,
    hash_refresh_token,
    verify_csrf_token,
    verify_password,
)
from app.domains.auth.models import AuthSession, EmailVerificationToken, PasswordResetToken
from app.domains.auth.repositories import (
    AuthSessionRepository,
    EmailVerificationTokenRepository,
    PasswordResetTokenRepository,
)
from app.domains.auth.schemas import (
    AuthTokens,
    ChangePassword,
    CurrentUser,
    ForgotPassword,
    ResetPassword,
    UserLogin,
    UserRegister,
    VerifyEmail,
)
from app.domains.tarjeta.schemas import TarjetaCreateNested
from app.domains.tarjeta.services import TarjetaService
from app.domains.usuario.models import Usuario
from app.domains.usuario.repositories import UsuarioRepository
from app.domains.usuario.services import UsuarioService
from app.integrations.resend import ResendService
from app.shared.enums import Role
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException


logger = get_logger(__name__)

# Motivos de revocación de una sesión (auth_sessions.revocation_reason).
REVOCATION_ROTATED = "rotated"
REVOCATION_REUSE_DETECTED = "reuse_detected"
REVOCATION_LOGOUT = "logout"
REVOCATION_PASSWORD_CHANGED = "password_changed"
REVOCATION_PASSWORD_RESET = "password_reset"
REVOCATION_USER_UNAVAILABLE = "user_unavailable"

IP_ADDRESS_MAX_LENGTH = 45


def _invalid_credentials() -> AppException:
    # El mismo mensaje si el email no existe o la contraseña no coincide.
    return AppException("Email o contraseña incorrectos.", status.HTTP_401_UNAUTHORIZED, ErrorCode.AUTHENTICATION_FAILED)


def _inactive_account() -> AppException:
    return AppException("La cuenta está dada de baja.", status.HTTP_403_FORBIDDEN, ErrorCode.PERMISSION_DENIED)


def _refresh_failed() -> AppException:
    return AppException("La sesión no es válida o venció.", status.HTTP_401_UNAUTHORIZED, ErrorCode.REFRESH_FAILED)


def _invalid_link() -> AppException:
    return AppException(
        "Los datos enviados no son válidos.",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorCode.VALIDATION_ERROR,
        details={"token": "El enlace no es válido, ya se usó o venció."},
    )


def _is_pending(token: PasswordResetToken | EmailVerificationToken | None, now: datetime) -> bool:
    return token is not None and token.used_at is None and token.revoked_at is None and token.expires_at > now


class AuthService:
    @staticmethod
    async def register(db_session: AsyncSession, data: UserRegister, settings: Settings) -> None:
        """
        Usuario (rol user, plan free, email sin verificar) y su tarjeta con todo su
        árbol, en una sola transacción: si el email o el slug ya están en uso (409),
        no se crea nada. Envía el enlace de verificación. No inicia sesión.
        """
        usuario = await UsuarioService.add_new(
            db_session, email=data.email, password=data.password, rol=Role.USER, created_by=None
        )
        usuario.created_by = usuario.id
        # Sin imágenes: el registro no las acepta, así que no hay nada que confirmar.
        await TarjetaService.add_new(
            db_session,
            TarjetaCreateNested(**data.tarjeta.model_dump(exclude_unset=True)),
            user_id=usuario.id,
            created_by=usuario.id,
            settings=settings,
        )
        token = await AuthService._issue_email_verification(db_session, usuario.id, settings)
        await db_session.commit()
        await AuthService._send_verification_email(settings, usuario.email, token)

    @staticmethod
    async def login(
        db_session: AsyncSession,
        data: UserLogin,
        settings: Settings,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthTokens:
        usuario = await UsuarioRepository.get_by_email(db_session, data.email)
        # Sin usuario se verifica un hash de relleno: tarda lo mismo y no revela qué emails existen.
        password_ok = verify_password(data.password, usuario.password_hash if usuario else DUMMY_PASSWORD_HASH)
        if usuario is None or not password_ok:
            raise _invalid_credentials()
        if not usuario.is_active:
            raise _inactive_account()
        _, tokens = AuthService._open_session(
            db_session, usuario, settings, user_agent=user_agent, ip_address=ip_address
        )
        await db_session.commit()
        return tokens

    @staticmethod
    async def refresh(
        db_session: AsyncSession,
        refresh_token: str | None,
        csrf_token: str | None,
        settings: Settings,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthTokens:
        """Rota la sesión: la anterior queda revocada con replaced_by apuntando a la nueva."""
        if not refresh_token:
            raise _refresh_failed()
        if not csrf_token or not verify_csrf_token(refresh_token, csrf_token, settings):
            raise AppException("Token CSRF inválido.", status.HTTP_403_FORBIDDEN, ErrorCode.CSRF_INVALID)

        now = utc_now()
        session = await AuthSessionRepository.get_by_token_hash(db_session, hash_refresh_token(refresh_token))
        if session is None:
            raise _refresh_failed()
        if session.revoked_at is not None:
            if session.replaced_by is not None:
                # Un token ya rotado volvió a usarse: alguien lo copió. Cae la familia entera.
                await AuthSessionRepository.revoke_family(db_session, session.family_id, now, REVOCATION_REUSE_DETECTED)
                await db_session.commit()
            raise _refresh_failed()
        if session.expires_at <= now:
            raise _refresh_failed()

        usuario = await UsuarioRepository.get(db_session, session.user_id)
        if usuario is None or not usuario.is_active:
            AuthService._revoke(session, now, REVOCATION_USER_UNAVAILABLE)
            await db_session.commit()
            raise _refresh_failed()

        # El rol sale de la base: un cambio de rol rige desde el siguiente refresh.
        new_session, tokens = AuthService._open_session(
            db_session,
            usuario,
            settings,
            family_id=session.family_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        # replaced_by es una foreign key: la sesión nueva se inserta antes de apuntarla.
        await db_session.flush()
        AuthService._revoke(session, now, REVOCATION_ROTATED)
        session.replaced_by = new_session.id
        session.last_used_at = now
        await db_session.commit()
        return tokens

    @staticmethod
    async def logout(db_session: AsyncSession, refresh_token: str | None) -> None:
        """Idempotente: sin cookie o con una sesión ya revocada no hace nada."""
        if not refresh_token:
            return
        session = await AuthSessionRepository.get_by_token_hash(db_session, hash_refresh_token(refresh_token))
        if session is not None and session.revoked_at is None:
            AuthService._revoke(session, utc_now(), REVOCATION_LOGOUT)
            await db_session.commit()

    @staticmethod
    async def change_password(
        db_session: AsyncSession,
        data: ChangePassword,
        actor: CurrentUser,
        settings: Settings,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthTokens:
        """Revoca todas las sesiones y abre una nueva para el dispositivo que la cambió."""
        usuario = await UsuarioService.get(db_session, actor.id)
        if not usuario.is_active:
            raise _inactive_account()
        if not verify_password(data.current_password, usuario.password_hash):
            raise AppException(
                "La contraseña actual no es correcta.",
                status.HTTP_401_UNAUTHORIZED,
                ErrorCode.AUTHENTICATION_FAILED,
                details={"current_password": "No coincide."},
            )
        now = utc_now()
        usuario.password_hash = hash_password(data.new_password)
        usuario.updated_at = now
        usuario.updated_by = usuario.id
        await AuthSessionRepository.revoke_all_for_user(db_session, usuario.id, now, REVOCATION_PASSWORD_CHANGED)
        await PasswordResetTokenRepository.revoke_pending_for_user(db_session, usuario.id, now)
        _, tokens = AuthService._open_session(
            db_session, usuario, settings, user_agent=user_agent, ip_address=ip_address
        )
        await db_session.commit()
        return tokens

    @staticmethod
    async def forgot_password(db_session: AsyncSession, data: ForgotPassword, settings: Settings) -> None:
        """Responde igual exista o no el email, para no revelar qué cuentas existen."""
        usuario = await UsuarioRepository.get_by_email(db_session, data.email)
        if usuario is None or not usuario.is_active:
            return
        token = await AuthService._issue_one_time_token(
            db_session,
            PasswordResetToken,
            usuario.id,
            utc_now() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
        )
        await db_session.commit()
        link = f"{settings.AUTH_FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
        await AuthService._send_email(
            settings,
            to=usuario.email,
            subject="Restablece tu contraseña",
            html=(
                "<p>Recibimos una solicitud para restablecer tu contraseña.</p>"
                f'<p><a href="{link}">Elegir una contraseña nueva</a></p>'
                f"<p>El enlace vence en {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutos. "
                "Si no lo pediste, ignora este correo.</p>"
            ),
            text=f"Restablece tu contraseña: {link}",
        )

    @staticmethod
    async def reset_password(db_session: AsyncSession, data: ResetPassword) -> None:
        """Cambia la contraseña con el token del correo y cierra todas las sesiones."""
        now = utc_now()
        token = await PasswordResetTokenRepository.get_by_token_hash(db_session, hash_one_time_token(data.token))
        if not _is_pending(token, now):
            raise _invalid_link()
        usuario = await UsuarioRepository.get(db_session, token.user_id)
        if usuario is None or not usuario.is_active:
            raise _invalid_link()
        usuario.password_hash = hash_password(data.new_password)
        usuario.updated_at = now
        usuario.updated_by = usuario.id
        token.used_at = now
        token.updated_at = now
        await AuthSessionRepository.revoke_all_for_user(db_session, usuario.id, now, REVOCATION_PASSWORD_RESET)
        await db_session.commit()

    @staticmethod
    async def verify_email(db_session: AsyncSession, data: VerifyEmail) -> None:
        now = utc_now()
        token = await EmailVerificationTokenRepository.get_by_token_hash(db_session, hash_one_time_token(data.token))
        if not _is_pending(token, now):
            raise _invalid_link()
        usuario = await UsuarioRepository.get(db_session, token.user_id)
        if usuario is None:
            raise _invalid_link()
        usuario.email_verified_at = now
        usuario.updated_at = now
        usuario.updated_by = usuario.id
        token.used_at = now
        token.updated_at = now
        await db_session.commit()

    @staticmethod
    async def resend_verification(db_session: AsyncSession, actor: CurrentUser, settings: Settings) -> None:
        """Nuevo enlace al email actual; el anterior deja de servir."""
        usuario = await UsuarioService.get(db_session, actor.id)
        if usuario.email_verified_at is not None:
            raise AppException("El email ya está verificado.", status.HTTP_409_CONFLICT, ErrorCode.CONFLICT)
        token = await AuthService._issue_email_verification(db_session, usuario.id, settings)
        await db_session.commit()
        await AuthService._send_verification_email(settings, usuario.email, token)

    # ---------- Internos ----------

    @staticmethod
    def _open_session(
        db_session: AsyncSession,
        usuario: Usuario,
        settings: Settings,
        *,
        family_id: UUID | None = None,
        user_agent: str | None,
        ip_address: str | None,
    ) -> tuple[AuthSession, AuthTokens]:
        """Agrega a la sesión de base de datos una sesión nueva, sin commit."""
        refresh_token = create_refresh_token()
        now = utc_now()
        auth_session = AuthSession(
            user_id=usuario.id,
            family_id=family_id or uuid4(),
            refresh_token_hash=hash_refresh_token(refresh_token),
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip_address[:IP_ADDRESS_MAX_LENGTH] if ip_address else None,
            created_by=usuario.id,
        )
        db_session.add(auth_session)
        return auth_session, AuthTokens(
            access_token=create_access_token({"sub": str(usuario.id), "role": usuario.rol.value}, settings),
            refresh_token=refresh_token,
            csrf_token=create_csrf_token(refresh_token, settings),
        )

    @staticmethod
    def _revoke(session: AuthSession, now: datetime, reason: str) -> None:
        session.revoked_at = now
        session.revocation_reason = reason
        session.updated_at = now

    @staticmethod
    async def _issue_one_time_token(
        db_session: AsyncSession,
        model: type[PasswordResetToken] | type[EmailVerificationToken],
        user_id: UUID,
        expires_at: datetime,
    ) -> str:
        """Revoca el token pendiente anterior (índice único parcial) y crea uno nuevo."""
        now = utc_now()
        if model is PasswordResetToken:
            await PasswordResetTokenRepository.revoke_pending_for_user(db_session, user_id, now)
        else:
            await EmailVerificationTokenRepository.revoke_pending_for_user(db_session, user_id, now)
        token = create_one_time_token()
        db_session.add(
            model(
                user_id=user_id,
                token_hash=hash_one_time_token(token),
                created_at=now,
                updated_at=now,
                expires_at=expires_at,
                created_by=user_id,
            )
        )
        return token

    @staticmethod
    async def _issue_email_verification(db_session: AsyncSession, user_id: UUID, settings: Settings) -> str:
        expires_at = utc_now() + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
        return await AuthService._issue_one_time_token(db_session, EmailVerificationToken, user_id, expires_at)

    @staticmethod
    async def _send_verification_email(settings: Settings, email: str, token: str) -> None:
        link = f"{settings.AUTH_FRONTEND_URL.rstrip('/')}/verify-email?token={token}"
        await AuthService._send_email(
            settings,
            to=email,
            subject="Verifica tu email",
            html=(
                "<p>Confirma tu email para poder publicar tu tarjeta.</p>"
                f'<p><a href="{link}">Verificar mi email</a></p>'
                f"<p>El enlace vence en {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS} horas.</p>"
            ),
            text=f"Verifica tu email: {link}",
        )

    @staticmethod
    async def _send_email(settings: Settings, *, to: str, subject: str, html: str, text: str) -> None:
        """
        Se envía después del commit y nunca interrumpe la operación: si falla, se
        registra, y el usuario puede pedir el enlace otra vez.
        """
        try:
            await ResendService.send_email(settings, to=to, subject=subject, html=html, text=text)
        except Exception:
            logger.exception("No se pudo enviar el correo '%s'", subject)
