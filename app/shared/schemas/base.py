from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
