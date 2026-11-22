from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.domains.auth.schemas import CurrentUser, TokenClaims
from app.shared.enums import Action, Module, Role
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.services.permissions import has_permission


# auto_error=False permite que el header sea opcional (para endpoints públicos).
# El botón Authorize de Swagger envía un formulario OAuth2 (username, password):
# por eso apunta a /auth/token y no a /auth/login, que recibe JSON.
OAUTH2_TOKEN_URL = "api/v1/auth/token"
OAUTH2_REFRESH_URL = "api/v1/auth/refresh"
OAUTH2_SCHEME_NAME = "BearerAuth"
OAUTH2_DESCRIPTION = "JWT de acceso enviado mediante Authorization: Bearer."

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=OAUTH2_TOKEN_URL,
    refreshUrl=OAUTH2_REFRESH_URL,
    scheme_name=OAUTH2_SCHEME_NAME,
    description=OAUTH2_DESCRIPTION,
    auto_error=False,
)


def _get_token_claims(token: str | None, settings: Settings) -> TokenClaims:
    if token is None:
        raise AppException(
            "Token de autenticación requerido.",
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.TOKEN_REQUIRED,
        )

    payload = decode_access_token(token, settings)
    if payload is None:
        raise AppException(
            "Token inválido.",
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.TOKEN_INVALID,
        )

    try:
        return TokenClaims.model_validate(payload)
    except ValidationError as error:
        raise AppException(
            "Token inválido.",
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.TOKEN_INVALID,
        ) from error


def _ensure_permission(
    current_user: CurrentUser,
    module: Module,
    action: Action,
) -> None:
    if not has_permission(current_user.role, module, action):
        raise AppException(
            "No tienes permisos para realizar esta acción.",
            status.HTTP_403_FORBIDDEN,
            ErrorCode.PERMISSION_DENIED,
        )


def _ensure_role(
    current_user: CurrentUser,
    allowed_roles: set[Role] | frozenset[Role],
) -> None:
    if current_user.role not in allowed_roles:
        raise AppException(
            "No tienes permisos para realizar esta acción.",
            status.HTTP_403_FORBIDDEN,
            ErrorCode.PERMISSION_DENIED,
        )


def _principal_from_claims(request: Request, claims: TokenClaims) -> CurrentUser:
    """
    El actor sale del token, sin consultar la base: los permisos funcionan sin
    ningún dominio de usuarios. Un cambio de rol o una eliminación rige cuando
    el access token vence (ACCESS_TOKEN_EXPIRE_MINUTES). Un proyecto que
    necesite revocarlo al instante carga aquí al usuario desde su repository.
    """
    current_user = CurrentUser(id=claims.sub, role=claims.role)
    # Lo usa el handler global para registrar quién provocó un error.
    request.state.user = current_user
    return current_user


async def get_current_principal(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    return _principal_from_claims(request, _get_token_claims(token, settings))


async def get_current_principal_optional(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser | None:
    if token is None:
        return None
    return _principal_from_claims(request, _get_token_claims(token, settings))


def require_permission(
    module: Module,
    action: Action,
) -> Callable[..., Awaitable[CurrentUser]]:
    async def dependency(
        current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    ) -> CurrentUser:
        _ensure_permission(current_user, module, action)
        return current_user

    return dependency


def require_role(
    *allowed_roles: Role,
) -> Callable[..., Awaitable[CurrentUser]]:
    allowed_role_set = frozenset(allowed_roles)

    async def dependency(
        current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    ) -> CurrentUser:
        _ensure_role(current_user, allowed_role_set)
        return current_user

    return dependency
