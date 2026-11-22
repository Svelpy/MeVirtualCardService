"""
Reglas de los ejemplos de documentación (AGENTS.md §20), para todos los schemas
de todos los dominios: cada schema expuesto define un ejemplo que pasa su propia
validación, contiene todos sus campos (también los embebidos) en el orden en que
se declaran, no contiene null y es coherente.
"""

import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest
from pydantic import BaseModel

import app.domains
from app.shared.schemas.base import SchemaBase


def _schema_classes() -> list[type[BaseModel]]:
    classes = []
    for module_info in pkgutil.iter_modules(app.domains.__path__):
        if not (Path(app.domains.__path__[0]) / module_info.name / "schemas.py").exists():
            continue
        module = importlib.import_module(f"app.domains.{module_info.name}.schemas")
        for name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseModel)
                and obj.__module__ == module.__name__
                and not name.startswith("_")
            ):
                classes.append(obj)
    return classes


def _example(schema: type[BaseModel]) -> dict | None:
    extra = schema.model_config.get("json_schema_extra")
    return extra.get("example") if isinstance(extra, dict) else None


SCHEMAS = _schema_classes()
WITH_EXAMPLE = [schema for schema in SCHEMAS if _example(schema) is not None]


def _check_complete(example: object, instance: BaseModel, path: str) -> None:
    assert isinstance(example, dict), path
    fields = list(type(instance).model_fields)
    assert list(example) == fields, f"{path}: campos faltantes o fuera de orden"
    for key in fields:
        value = example[key]
        assert value is not None, f"{path}.{key} es null"
        attribute = getattr(instance, key)
        if isinstance(attribute, BaseModel):
            _check_complete(value, attribute, f"{path}.{key}")
        elif isinstance(attribute, list):
            assert value, f"{path}.{key}: la lista del ejemplo está vacía"
            for index, (item_example, item) in enumerate(zip(value, attribute)):
                if isinstance(item, BaseModel):
                    _check_complete(item_example, item, f"{path}.{key}[{index}]")


def test_hay_schemas_de_dominio():
    assert len(WITH_EXAMPLE) > 50


@pytest.mark.parametrize("schema", [s for s in SCHEMAS if issubclass(s, SchemaBase)], ids=lambda s: s.__name__)
def test_todo_schema_de_dominio_define_un_ejemplo(schema):
    assert _example(schema) is not None


@pytest.mark.parametrize("schema", WITH_EXAMPLE, ids=lambda s: s.__name__)
def test_el_ejemplo_pasa_su_validacion_y_esta_completo(schema):
    example = _example(schema)
    instance = schema.model_validate(example)
    _check_complete(example, instance, schema.__name__)


@pytest.mark.parametrize("schema", SCHEMAS, ids=lambda s: s.__name__)
def test_genera_su_json_schema_para_openapi(schema):
    assert schema.model_json_schema(mode="validation")
    assert schema.model_json_schema(mode="serialization")


@pytest.mark.parametrize(
    "schema", [s for s in WITH_EXAMPLE if s.__name__.endswith("ResponseAudit")], ids=lambda s: s.__name__
)
def test_el_ejemplo_de_auditoria_es_coherente(schema):
    example = _example(schema)
    assert example["is_deleted"] is True
    assert list(example)[-5:] == ["created_by", "updated_by", "is_deleted", "deleted_at", "deleted_by"]
