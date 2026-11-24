from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.domains.tarjeta.schemas import TARJETA_REGISTRO_EXAMPLE, TarjetaRegistro
from app.shared.enums import Role
from app.shared.services.validators import (
    validator_email,
    validator_non_empty_text,
    validator_password,
)


class UserRegister(BaseModel):
    """
    Registro público: crea un usuario con rol user, plan free y el email sin
    verificar, y su tarjeta (obligatoria) en la misma transacción. Sin verificar
    puede iniciar sesión, pero no publicar su tarjeta.
    """

    email: EmailStr = Field(max_length=255)
    password: str
    tarjeta: TarjetaRegistro

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str:
        return validator_email(value)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: object) -> str:
        return validator_password(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"email": "ana@example.com", "password": "ClaveSegura123", "tarjeta": TARJETA_REGISTRO_EXAMPLE}
        },
    )


class UserLogin(BaseModel):
    email: EmailStr = Field(max_length=255)
    # Sin reglas de longitud: una contraseña que no cumple la política actual
    # debe responder 401 como cualquier credencial incorrecta, no 422.
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str:
        return validator_email(value)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("La contraseña debe ser texto.")
        return value

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"email": "ana@example.com", "password": "ClaveSegura123"}},
    )


class ForgotPassword(BaseModel):
    """Siempre responde igual, exista o no el email, para no revelar cuentas."""

    email: EmailStr = Field(max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str:
        return validator_email(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"email": "ana@example.com"}},
    )


class VerifyEmail(BaseModel):
    """Verificación del email con el token recibido por correo."""

    token: str = Field(min_length=1, max_length=128)

    @field_validator("token", mode="before")
    @classmethod
    def validate_token(cls, value: object) -> str:
        return validator_non_empty_text(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"token": "<token-recibido-por-correo>"}},
    )


class ResetPassword(BaseModel):
    """Restablecimiento de contraseña con el token recibido por correo."""

    token: str = Field(min_length=1, max_length=128)
    new_password: str

    @field_validator("token", mode="before")
    @classmethod
    def validate_token(cls, value: object) -> str:
        return validator_non_empty_text(value)

    @field_validator("new_password", mode="before")
    @classmethod
    def validate_new_password(cls, value: object) -> str:
        return validator_password(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "token": "<token-recibido-por-correo>",
                "new_password": "NuevaClave123",
            }
        },
    )


class ChangePassword(BaseModel):
    """
    Cambio de contraseña del usuario autenticado. Revoca sus otras sesiones y
    abre una nueva para el dispositivo que la cambió.
    """

    # La actual no pasa por la política: si no coincide, el service responde 401.
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str

    @field_validator("current_password", mode="before")
    @classmethod
    def validate_current_password(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("La contraseña debe ser texto.")
        return value

    @field_validator("new_password", mode="before")
    @classmethod
    def validate_new_password(cls, value: object) -> str:
        return validator_password(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"current_password": "ClaveSegura123", "new_password": "OtraClaveSegura456"}
        }
    )


class TokenResponse(BaseModel):
    """Tokens que pueden exponerse al cliente."""

    access_token: str
    csrf_token: str
    token_type: Literal["bearer"] = "bearer"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "<jwt-access-token>",
                "csrf_token": "<csrf-token>",
                "token_type": "bearer",
            }
        }
    )


class AuthTokens(BaseModel):
    """Resultado interno que incluye el refresh token sensible."""

    access_token: str
    refresh_token: str
    csrf_token: str

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "access_token": "<jwt-access-token>",
                "refresh_token": "<refresh-token>",
                "csrf_token": "<csrf-token>",
            }
        },
    )


class CurrentUser(BaseModel):
    """Principal autenticado construido desde el usuario vigente en PostgreSQL."""

    id: UUID
    role: Role

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"id": "8f14e45f-ceea-467a-9575-6b3f0c1a2b3c", "role": "user"}},
    )


class TokenClaims(BaseModel):
    """Claims obligatorios del access token emitido por el backend."""

    sub: UUID
    role: Role
    iat: datetime
    exp: datetime
    jti: UUID

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "sub": "8f14e45f-ceea-467a-9575-6b3f0c1a2b3c",
                "role": "user",
                "iat": "2026-02-01T09:00:00Z",
                "exp": "2026-02-01T09:15:00Z",
                "jti": "0f8fad5b-d9cb-469f-a165-70867728950e",
            }
        },
    )

