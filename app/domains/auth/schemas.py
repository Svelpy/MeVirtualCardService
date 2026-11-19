from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.enums import Role
from app.shared.services.validators import (
    validator_non_empty_text,
    validator_password,
)


class UserLogin(BaseModel):
    pass


class ForgotPassword(BaseModel):
    pass


class ResetPassword(BaseModel):
    """Restablecimiento de contraseña con el token recibido por correo."""

    token: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=20)

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

    model_config = ConfigDict(extra="forbid")


class CurrentUser(BaseModel):
    """Principal autenticado construido desde el usuario vigente en PostgreSQL."""

    id: UUID
    role: Role
    sucursal_id: UUID | None

    model_config = ConfigDict(extra="forbid")


class TokenClaims(BaseModel):
    """Claims obligatorios del access token emitido por el backend."""

    sub: UUID
    role: Role
    iat: datetime
    exp: datetime
    jti: UUID

    model_config = ConfigDict(extra="forbid")

