"""
Reglas de los ejemplos de documentación (AGENTS.md §20). El frontend aprende cada
request y cada respuesta por su ejemplo en Swagger, así que para todos los schemas
de todos los dominios el ejemplo:

- existe y pasa su propia validación;
- contiene todos sus campos (también los embebidos) en el orden en que se declaran;
- no contiene null, "" ni colecciones vacías;
- trae al menos 3 objetos en cada lista (un solo elemento no muestra la variedad);
- es coherente (la auditoría de un registro eliminado tiene sus datos de baja).

Se comprueba sobre los schemas y sobre el OpenAPI que publica la app, que es lo
que ve el frontend (por ejemplo, la página de PaginatedResponse).

La única ausencia permitida está en EXCEPTIONS: un campo que el backend rechaza
en ese contexto no se muestra, porque el ejemplo enseñaría un request inválido.
"""

import importlib
import inspect
import pkgutil
import re
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

import app.domains
from app.main import app as fastapi_app
from app.shared.schemas.base import SchemaBase
from app.shared.schemas.examples import EXAMPLE_COUNT


# (schema, ruta dentro de su ejemplo) → campo que no se muestra.
EXCEPTIONS = {
    # Al crear la vitrina las categorías no tienen id: un item no puede apuntarlas (422).
    ("VitrinaCreateNested", "items[]"): {"categoria_id"},
    ("TarjetaCreateNested", "vitrina.items[]"): {"categoria_id"},
}


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


def _omitted(root: str, path: str) -> set[str]:
    return EXCEPTIONS.get((root, re.sub(r"\[\d+\]", "[]", path)), set())


SCHEMAS = _schema_classes()
WITH_EXAMPLE = [schema for schema in SCHEMAS if _example(schema) is not None]
WITH_PAGE = [schema for schema in SCHEMAS if "PAGE_EXAMPLES" in vars(schema)]


def _check_complete(example: object, instance: BaseModel, root: str, path: str = "") -> None:
    where = f"{root}.{path}" if path else root
    assert isinstance(example, dict), where
    fields = [field for field in type(instance).model_fields if field not in _omitted(root, path)]
    assert list(example) == fields, f"{where}: campos faltantes o fuera de orden"
    for key in fields:
        value = example[key]
        child = f"{path}.{key}" if path else key
        assert value is not None and value != "", f"{root}.{child} está vacío"
        attribute = getattr(instance, key)
        if isinstance(attribute, BaseModel):
            _check_complete(value, attribute, root, child)
        elif isinstance(attribute, list):
            assert len(value) >= EXAMPLE_COUNT, f"{root}.{child}: la lista trae {len(value)} (mínimo {EXAMPLE_COUNT})"
            for index, (item_example, item) in enumerate(zip(value, attribute)):
                if isinstance(item, BaseModel):
                    _check_complete(item_example, item, root, f"{child}[{index}]")
        elif isinstance(attribute, dict):
            assert value, f"{root}.{child}: el diccionario del ejemplo está vacío"


# ---------- Schemas de dominio ----------

def test_hay_schemas_de_dominio():
    assert len(WITH_EXAMPLE) > 50


@pytest.mark.parametrize("schema", SCHEMAS, ids=lambda s: s.__name__)
def test_todo_schema_de_dominio_define_un_ejemplo(schema):
    assert _example(schema) is not None


@pytest.mark.parametrize("schema", WITH_EXAMPLE, ids=lambda s: s.__name__)
def test_el_ejemplo_pasa_su_validacion_y_esta_completo(schema):
    example = _example(schema)
    instance = schema.model_validate(example)
    _check_complete(example, instance, schema.__name__)


@pytest.mark.parametrize("schema", WITH_PAGE, ids=lambda s: s.__name__)
def test_las_variantes_de_un_listado_son_validas_completas_y_distintas(schema):
    # PaginatedResponse[schema] las publica como data del ejemplo de su página.
    examples = schema.PAGE_EXAMPLES
    assert len(examples) >= EXAMPLE_COUNT
    assert len({example["id"] for example in examples}) == len(examples)
    for example in examples:
        _check_complete(example, schema.model_validate(example), schema.__name__)


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


def test_los_schemas_de_dominio_heredan_de_schema_base_o_son_de_auth():
    # Los de auth no usan SchemaBase, pero se revisan igual por estar en SCHEMAS.
    assert all(issubclass(s, SchemaBase) or s.__module__.startswith("app.domains.auth") for s in SCHEMAS)


# ---------- Lo que publica Swagger ----------

@cache
def _components() -> dict[str, Any]:
    return fastapi_app.openapi()["components"]["schemas"]


def _resolve(schema: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in schema:
        schema = _components()[schema["$ref"].rsplit("/", 1)[-1]]
    return schema


def _variants(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Las ramas no nulas de un anyOf/oneOf (X | None)."""
    schema = _resolve(schema)
    branches = schema.get("anyOf") or schema.get("oneOf")
    if not branches:
        return [schema]
    return [_resolve(branch) for branch in branches if branch.get("type") != "null"]


def _check_openapi(schema: dict[str, Any], value: Any, path: str, root: str, errors: list[str]) -> None:
    if value is None or value == "" or value == {} or value == []:
        errors.append(f"{root}: {path or '(raíz)'} está vacío")
        return
    variants = _variants(schema)
    if isinstance(value, dict):
        objects = [v for v in variants if "properties" in v]
        if not objects:
            return
        properties = next((v for v in objects if set(v["properties"]) == set(value)), objects[0])["properties"]
        for name in set(properties) - set(value) - _omitted(root, path):
            errors.append(f"{root}: falta {path + '.' if path else ''}{name}")
        for name, item in value.items():
            if name in properties:
                _check_openapi(properties[name], item, f"{path}.{name}" if path else name, root, errors)
    elif isinstance(value, list):
        if len(value) < EXAMPLE_COUNT:
            errors.append(f"{root}: {path} trae {len(value)} elementos (mínimo {EXAMPLE_COUNT})")
        arrays = [v for v in variants if v.get("type") == "array" and "items" in v]
        for item in value if arrays else []:
            _check_openapi(arrays[0]["items"], item, f"{path}[]", root, errors)


def _published() -> list[str]:
    # Fuera: los formularios que arma FastAPI (Body_...) y su propio error de validación.
    return sorted(
        name
        for name, schema in _components().items()
        if "enum" not in schema and not name.startswith(("Body_", "HTTPValidationError", "ValidationError"))
    )


@pytest.mark.parametrize("name", _published())
def test_cada_schema_publicado_en_swagger_tiene_un_ejemplo_completo(name):
    schema = _components()[name]
    assert "example" in schema, f"{name} no tiene ejemplo en Swagger"
    errors: list[str] = []
    _check_openapi(schema, schema["example"], "", name, errors)
    assert not errors, "\n".join(errors)
