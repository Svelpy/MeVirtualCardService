import importlib
import pkgutil
from pathlib import Path

import pytest
from sqlalchemy.orm import configure_mappers
from sqlmodel import SQLModel

import app.domains


ENV_PY = Path(__file__).resolve().parents[1] / "migrations" / "env.py"


def _domains_with_models() -> list[str]:
    return sorted(
        module.name
        for module in pkgutil.iter_modules(app.domains.__path__)
        if (Path(app.domains.__path__[0]) / module.name / "models.py").exists()
    )


def test_env_importa_todos_los_models():
    # Un models.py que no se importa en env.py no existe para Alembic, y
    # autogenerate propondría eliminar su tabla (AGENTS.md §8).
    env = ENV_PY.read_text(encoding="utf-8")
    missing = [d for d in _domains_with_models() if f"import app.domains.{d}.models" not in env]
    assert missing == []


def test_los_mappers_se_configuran():
    for domain in _domains_with_models():
        importlib.import_module(f"app.domains.{domain}.models")
    configure_mappers()
    assert "tarjeta" in SQLModel.metadata.tables


def test_las_relaciones_no_cargan_de_forma_implicita():
    # La sesión es async: una carga implícita fallaría (AGENTS.md §18).
    for domain in _domains_with_models():
        importlib.import_module(f"app.domains.{domain}.models")
    configure_mappers()
    for mapper in SQLModel._sa_registry.mappers:
        for relationship in mapper.relationships:
            assert relationship.lazy == "raise", f"{mapper.class_.__name__}.{relationship.key}"


def test_la_app_configura_sus_mappers_sin_ayuda_de_los_tests():
    # conftest importa todos los models; la app real solo los que importan sus
    # routes. Un proceso limpio comprueba que con eso alcanza.
    import subprocess
    import sys

    code = "import app.main; from sqlalchemy.orm import configure_mappers; configure_mappers()"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ENV_PY.parents[1])
    assert result.returncode == 0, result.stderr[-2000:]


def _domains_with_repositories() -> list[str]:
    return sorted(
        module.name
        for module in pkgutil.iter_modules(app.domains.__path__)
        if (Path(app.domains.__path__[0]) / module.name / "repositories.py").exists()
    )


@pytest.mark.parametrize("domain", _domains_with_repositories())
def test_cada_repository_carga_los_models_de_sus_relaciones(domain):
    # Un job o un seed importa services y repositories sin la app: cada
    # repository debe cargar los models que sus Relationship() nombran como texto.
    import subprocess
    import sys

    code = f"import app.domains.{domain}.repositories; from sqlalchemy.orm import configure_mappers; configure_mappers()"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ENV_PY.parents[1])
    assert result.returncode == 0, result.stderr[-800:]
