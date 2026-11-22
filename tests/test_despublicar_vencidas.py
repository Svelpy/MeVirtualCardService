"""Job jobs/despublicar_vencidas.py contra la base de desarrollo, dentro de una transacción revertida."""

import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.base_model import utc_now
from app.domains.tarjeta.models import Tarjeta
from app.domains.tarjeta.services import TarjetaService
from tests.conftest import auth_header, create_usuario


ROOT = Path(__file__).resolve().parents[1]


async def _tarjeta(db_session, usuario, *, is_public: bool = True, is_deleted: bool = False) -> Tarjeta:
    tarjeta = Tarjeta(
        user_id=usuario.id,
        slug=f"t-{uuid4().hex[:8]}",
        rubro="Pediatría",
        nombres="Ana",
        is_public=is_public,
        published_at=utc_now() if is_public else None,
        is_deleted=is_deleted,
    )
    db_session.add(tarjeta)
    await db_session.commit()
    return tarjeta


async def _is_public(db_session, tarjeta: Tarjeta) -> bool:
    query = select(Tarjeta.is_public).where(Tarjeta.id == tarjeta.id).execution_options(populate_existing=True)
    return (await db_session.execute(query)).scalar_one()


async def test_despublica_solo_las_tarjetas_con_el_plan_vencido(db_session):
    vencido = await create_usuario(db_session, "vencido@test.example.com", plan_vence_at_days=-1)
    vigente = await create_usuario(db_session, "vigente@test.example.com", plan_vence_at_days=10)
    eliminado = await create_usuario(db_session, "eliminado@test.example.com", plan_vence_at_days=-1)
    publica_vencida = await _tarjeta(db_session, vencido)
    publica_vigente = await _tarjeta(db_session, vigente)
    eliminada = await _tarjeta(db_session, eliminado, is_deleted=True)

    # Otras tarjetas vencidas de la base de desarrollo también cuentan: al menos la nuestra.
    assert await TarjetaService.despublicar_vencidas(db_session) >= 1

    assert await _is_public(db_session, publica_vencida) is False
    assert await _is_public(db_session, publica_vigente) is True
    assert await _is_public(db_session, eliminada) is True  # una tarjeta eliminada no se toca

    await db_session.refresh(publica_vencida)
    assert publica_vencida.updated_by is None  # lo hizo el sistema
    assert publica_vencida.published_at is not None  # conserva cuándo se publicó


async def test_repetirlo_no_cambia_nada(db_session):
    vencido = await create_usuario(db_session, "vencido@test.example.com", plan_vence_at_days=-1)
    tarjeta = await _tarjeta(db_session, vencido)
    await TarjetaService.despublicar_vencidas(db_session)
    await db_session.refresh(tarjeta)
    updated_at = tarjeta.updated_at

    await TarjetaService.despublicar_vencidas(db_session)
    await db_session.refresh(tarjeta)
    assert tarjeta.updated_at == updated_at


def test_el_job_arranca_en_un_proceso_limpio():
    # Sus imports bastan para configurar los mappers, como en la imagen de Docker.
    code = (
        "import jobs.despublicar_vencidas; "
        "from sqlalchemy.orm import configure_mappers; configure_mappers()"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr[-2000:]


# ---------- POST /tarjetas/despublicar-vencidas ----------

URL = "/api/v1/tarjetas/despublicar-vencidas"


async def test_un_admin_lo_dispara_y_queda_como_quien_la_despublico(client, db_session, admin):
    vencido = await create_usuario(db_session, "vencido@test.example.com", plan_vence_at_days=-1)
    vigente = await create_usuario(db_session, "vigente@test.example.com", plan_vence_at_days=10)
    publica_vencida = await _tarjeta(db_session, vencido)
    publica_vigente = await _tarjeta(db_session, vigente)

    response = await client.post(URL, headers=auth_header(admin))
    assert response.status_code == 200
    assert response.json()["despublicadas"] >= 1  # también otras vencidas de la base de desarrollo
    assert await _is_public(db_session, publica_vencida) is False
    assert await _is_public(db_session, publica_vigente) is True
    await db_session.refresh(publica_vencida)
    assert publica_vencida.updated_by == admin.id

    # Repetirlo no encuentra nada nuevo que despublicar entre las nuestras.
    assert (await client.post(URL, headers=auth_header(admin))).status_code == 200
    assert await _is_public(db_session, publica_vigente) is True


async def test_el_superadmin_tambien_y_el_user_no(client, superadmin, user):
    assert (await client.post(URL, headers=auth_header(superadmin))).status_code == 200
    response = await client.post(URL, headers=auth_header(user))
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


async def test_sin_token_responde_401(client):
    assert (await client.post(URL)).status_code == 401
