from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# Máximo de una columna smallint de PostgreSQL (orden, duración, tipografía...).
SMALLINT_MAX = 32767

# Campos de AuditMixin para los ejemplos de <X>ResponseAudit. Sin valores null:
# un registro con deleted_at tiene is_deleted true (AGENTS.md §20).
AUDIT_EXAMPLE: dict[str, object] = {
    "created_by": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
    "updated_by": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
    "is_deleted": True,
    "deleted_at": "2026-03-01T10:00:00Z",
    "deleted_by": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
}


def reject_null(value: object) -> object:
    """
    Primer paso del validador de un campo no nullable de un <X>Update: un null
    explícito responde 422 en vez de llegar a la base (AGENTS.md §20).
    """
    if value is None:
        raise ValueError("El campo no puede ser null.")
    return value


class SchemaBase(BaseModel):
    """Base de todos los schemas de dominio."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AuditMixin(SchemaBase):
    """Campos que solo expone <X>ResponseAudit; se hereda antes que <X>Response."""

    created_by: UUID | None
    updated_by: UUID | None
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: UUID | None
