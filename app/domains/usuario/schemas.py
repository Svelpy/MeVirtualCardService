from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import ConfigDict, EmailStr, Field, field_validator

from app.domains.plan.schemas import (
    PLAN_IDS,
    PLAN_REF_EXAMPLE,
    PLAN_REF_EXAMPLES,
    PLAN_RESPONSE_EXAMPLE,
    PlanRef,
    PlanResponse,
)
from app.shared.enums import Role
from app.shared.schemas.base import AUDIT_EXAMPLE, AuditMixin, SchemaBase, reject_null
from app.shared.services.validators import validator_email, validator_password


USUARIO_ID = "8f14e45f-ceea-467a-9575-6b3f0c1a2b3c"

USUARIO_RESPONSE_EXAMPLE = {
    "id": USUARIO_ID,
    "email": "ana@example.com",
    "rol": "user",
    "plan_id": "7b1e9c40-0000-4000-8000-000000000002",
    "plan_vence_at": "2027-01-15T14:30:00Z",
    "is_active": True,
    "email_verified_at": "2026-01-15T15:00:00Z",
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}
USUARIO_REF_EXAMPLE = {"id": USUARIO_ID, "email": "ana@example.com"}

USUARIO_RESPONSE_EXAMPLES = [
    USUARIO_RESPONSE_EXAMPLE,
    {
        "id": "8f14e45f-ceea-467a-9575-6b3f0c1a2b3d",
        "email": "luis.mamani@example.com",
        "rol": "admin",
        "plan_id": PLAN_IDS[2],
        "plan_vence_at": "2027-03-01T00:00:00Z",
        "is_active": True,
        "email_verified_at": "2026-01-10T12:00:00Z",
        "created_at": "2026-01-10T11:45:00Z",
        "updated_at": "2026-01-10T12:00:00Z",
    },
    {
        "id": "8f14e45f-ceea-467a-9575-6b3f0c1a2b3e",
        "email": "carla.rojas@example.com",
        "rol": "user",
        "plan_id": PLAN_IDS[0],
        "plan_vence_at": "2026-02-07T09:20:00Z",
        "is_active": False,
        "email_verified_at": "2026-01-31T09:30:00Z",
        "created_at": "2026-01-31T09:20:00Z",
        "updated_at": "2026-02-15T18:00:00Z",
    },
]
USUARIO_REF_EXAMPLES = [{"id": usuario["id"], "email": usuario["email"]} for usuario in USUARIO_RESPONSE_EXAMPLES]
_PLAN_REFS = {plan["id"]: plan for plan in PLAN_REF_EXAMPLES}


# =================================
# Ronda 1: schemas planos
# =================================

class UsuarioCreate(SchemaBase):
    """
    Alta por un admin. El plan (free), su vencimiento, is_active y la
    verificación del email los asigna el service; la jerarquía decide qué rol
    puede asignar el actor.
    """

    email: EmailStr = Field(max_length=255)
    password: str
    rol: Role = Role.USER

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str:
        return validator_email(value)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: object) -> str:
        return validator_password(value)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "ana@example.com", "password": "ClaveSegura123", "rol": "user"}
        }
    )


class UsuarioUpdate(SchemaBase):
    """Edición por un admin. Plan, is_active y contraseña tienen sus propios caminos."""

    email: EmailStr = Field(default=None, max_length=255)
    rol: Role = Field(default=None)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str:
        return validator_email(reject_null(value))

    model_config = ConfigDict(json_schema_extra={"example": {"email": "ana@example.com", "rol": "user"}})


class UsuarioUpdateMe(SchemaBase):
    """PATCH /usuarios/me: sin rol (AGENTS.md §24). Cambiar el email lo deja sin verificar."""

    email: EmailStr = Field(default=None, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str:
        return validator_email(reject_null(value))

    model_config = ConfigDict(json_schema_extra={"example": {"email": "ana.nueva@example.com"}})


class UsuarioResponse(SchemaBase):
    id: UUID
    email: str
    rol: Role
    plan_id: UUID
    plan_vence_at: datetime
    is_active: bool
    email_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": USUARIO_RESPONSE_EXAMPLE})


class UsuarioResponseAudit(AuditMixin, UsuarioResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**USUARIO_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class UsuarioRef(SchemaBase):
    id: UUID
    email: str

    model_config = ConfigDict(json_schema_extra={"example": USUARIO_REF_EXAMPLE})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class UsuarioResponseItemList(UsuarioResponse):
    plan: PlanRef

    # Ejemplo de GET /usuarios.
    PAGE_EXAMPLES: ClassVar[list[dict]] = [
        {**usuario, "plan": _PLAN_REFS[usuario["plan_id"]]} for usuario in USUARIO_RESPONSE_EXAMPLES
    ]

    model_config = ConfigDict(json_schema_extra={"example": {**USUARIO_RESPONSE_EXAMPLE, "plan": PLAN_REF_EXAMPLE}})


class UsuarioResponseDetail(UsuarioResponse):
    plan: PlanResponse

    model_config = ConfigDict(json_schema_extra={"example": {**USUARIO_RESPONSE_EXAMPLE, "plan": PLAN_RESPONSE_EXAMPLE}})
