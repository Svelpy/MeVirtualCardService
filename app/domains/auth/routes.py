from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import (
    AuthTokens,
    ChangePassword,
    CurrentUser,
    ForgotPassword,
    ResetPassword,
    TokenResponse,
    UserLogin,
    UserRegister,
    VerifyEmail,
)
from app.domains.auth.services import AuthService
from app.middlewares.limiter import limiter
from app.shared.errors.exceptions import body_validation_error
from app.shared.schemas.errors import error_responses


router = APIRouter(prefix="/auth", tags=["Autenticación"])

# La cookie del refresh token solo viaja a las rutas de auth.
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _client_info(request: Request) -> dict[str, str | None]:
    return {
        "user_agent": request.headers.get("user-agent"),
        "ip_address": request.client.host if request.client else None,
    }


def _token_response(response: Response, tokens: AuthTokens, settings: Settings) -> TokenResponse:
    """El refresh token va solo en la cookie HttpOnly; el CSRF token, en el body."""
    secure = settings.REFRESH_TOKEN_COOKIE_SECURE
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=tokens.refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        # En staging y producción el frontend vive en otro dominio: SameSite=None
        # exige Secure. La protección contra CSRF la da el header X-CSRF-Token.
        samesite="none" if secure else "lax",
    )
    return TokenResponse(access_token=tokens.access_token, csrf_token=tokens.csrf_token)


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    secure = settings.REFRESH_TOKEN_COOKIE_SECURE
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite="none" if secure else "lax",
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_class=Response,
    summary="Registrarse",
    description=(
        "Crea el usuario (plan free, email sin verificar) y su tarjeta, obligatoria, en una sola transacción, "
        "y envía el enlace de verificación del email. Si el email o el slug ya están en uso responde 409 y "
        "no crea nada. No inicia sesión: el siguiente paso es POST /auth/login."
    ),
    responses={
        # RFC 9110 §15.3.2: el cuerpo de un 201 es opcional; Location identifica el recurso creado.
        status.HTTP_201_CREATED: {
            "description": "Usuario y tarjeta creados. Sin contenido.",
            "headers": {
                "Location": {
                    "description": "El usuario creado: GET /api/v1/usuarios/me (requiere iniciar sesión).",
                    "schema": {"type": "string", "example": "/api/v1/usuarios/me"},
                }
            },
        },
        **error_responses(409, 422, 429, 500),
    },
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: UserRegister,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await AuthService.register(db_session, data, settings)
    return Response(status_code=status.HTTP_201_CREATED, headers={"Location": "/api/v1/usuarios/me"})


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
    description="Devuelve el access token y el CSRF token; el refresh token queda en una cookie HttpOnly.",
    responses=error_responses(401, 403, 422, 429, 500),
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    data: UserLogin,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    tokens = await AuthService.login(db_session, data, settings, **_client_info(request))
    return _token_response(response, tokens, settings)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Iniciar sesión con el formulario OAuth2 (Swagger)",
    description=(
        "El mismo login que /auth/login, con el formulario OAuth2 password: username es el email. "
        "Es el tokenUrl del botón Authorize de /docs; el frontend usa /auth/login con JSON."
    ),
    responses=error_responses(401, 403, 422, 429, 500),
)
@limiter.limit("5/minute")
async def login_oauth2(
    request: Request,
    response: Response,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        data = UserLogin(email=form.username, password=form.password)
    except ValidationError as error:
        # El mismo 422 que con JSON, con el nombre de campo del formulario.
        raise body_validation_error(error, renamed_fields={"email": "username"}) from error
    tokens = await AuthService.login(db_session, data, settings, **_client_info(request))
    return _token_response(response, tokens, settings)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar la sesión",
    description="Usa la cookie del refresh token y el header X-CSRF-Token. Rota la sesión.",
    responses=error_responses(401, 403, 429, 500),
)
@limiter.limit("20/minute")
async def refresh(
    request: Request,
    response: Response,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> TokenResponse:
    refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    tokens = await AuthService.refresh(db_session, refresh_token, x_csrf_token, settings, **_client_info(request))
    return _token_response(response, tokens, settings)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión",
    description="Revoca la sesión de la cookie y la borra. Sin cookie también responde 204.",
    responses=error_responses(500),
)
async def logout(
    request: Request,
    response: Response,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await AuthService.logout(db_session, request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME))
    _clear_refresh_cookie(response, settings)


@router.post(
    "/change-password",
    response_model=TokenResponse,
    summary="Cambiar mi contraseña",
    description="Cierra las demás sesiones y devuelve tokens nuevos para este dispositivo.",
    responses=error_responses(401, 403, 404, 422, 429, 500),
)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    response: Response,
    data: ChangePassword,
    current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    tokens = await AuthService.change_password(db_session, data, current_user, settings, **_client_info(request))
    return _token_response(response, tokens, settings)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Pedir el enlace para restablecer la contraseña",
    description="Responde 204 exista o no el email, para no revelar qué cuentas existen.",
    responses=error_responses(422, 429, 500),
)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPassword,
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await AuthService.forgot_password(db_session, data, settings)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Restablecer la contraseña",
    description="Usa el token del correo, una sola vez, y cierra todas las sesiones.",
    responses=error_responses(422, 429, 500),
)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    data: ResetPassword,
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await AuthService.reset_password(db_session, data)


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Verificar el email",
    description="Usa el token del correo, una sola vez.",
    responses=error_responses(422, 429, 500),
)
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    data: VerifyEmail,
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await AuthService.verify_email(db_session, data)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reenviar el enlace de verificación",
    description="Envía un enlace nuevo al email actual; el anterior deja de servir.",
    responses=error_responses(401, 404, 409, 429, 500),
)
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await AuthService.resend_verification(db_session, current_user, settings)
