from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ConfigDict, ValidationError

from app.shared.schemas.base import AuditMixin, SchemaBase
from app.shared.schemas.errors import ERROR_RESPONSES, error_responses


class EjemploCreate(SchemaBase):
    nombre: str

    model_config = ConfigDict(json_schema_extra={"example": {"nombre": "Ana"}})


class EjemploResponse(SchemaBase):
    id: UUID
    nombre: str
    created_at: datetime
    updated_at: datetime


class EjemploResponseAudit(AuditMixin, EjemploResponse):
    pass


def test_campos_extra_se_rechazan():
    with pytest.raises(ValidationError, match="extra"):
        EjemploCreate.model_validate({"nombre": "Ana", "rol": "ADMIN"})


def test_el_hijo_conserva_la_config_de_schemabase():
    assert EjemploCreate.model_config["extra"] == "forbid"
    assert EjemploCreate.model_config["from_attributes"] is True


def test_la_auditoria_queda_al_final():
    assert list(EjemploResponseAudit.model_fields) == [
        "id", "nombre", "created_at", "updated_at",
        "created_by", "updated_by", "is_deleted", "deleted_at", "deleted_by",
    ]


def test_error_responses_selecciona_codigos():
    assert error_responses(401, 404) == {401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404]}
