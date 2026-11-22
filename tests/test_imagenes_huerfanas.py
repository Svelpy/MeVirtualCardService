"""Limpieza de imágenes huérfanas: la integración con Cloudinary, el service, el endpoint y el job."""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cloudinary.api
import cloudinary.uploader
import pytest

import app.integrations.cloudinary as cloudinary_module
from app.integrations.cloudinary import CloudinaryService
from tests.conftest import PLAN_PRO_ID, auth_header, make_settings, uploaded_image_url


ROOT = Path(__file__).resolve().parents[1]
URL = "/api/v1/imagenes/limpiar-huerfanas"


# ---------- Integración (Cloudinary simulado a nivel de SDK) ----------

@pytest.fixture
def sdk(monkeypatch):
    """Reemplaza las llamadas del SDK de Cloudinary y registra lo que recibe."""
    calls: dict[str, list] = {"resources_by_tag": [], "delete_resources": [], "remove_tag": []}
    pages = [
        {
            "resources": [
                {"public_id": "proy_test/imagenes/vieja", "created_at": "2026-01-01T00:00:00Z", "secure_url": "https://x/vieja.jpg"},
                {"public_id": "proy_test/imagenes/nueva", "created_at": "2026-12-31T00:00:00Z", "secure_url": "https://x/nueva.jpg"},
            ],
            "next_cursor": "pagina-2",
        },
        {
            "resources": [
                # Otro entorno comparte la cuenta y la etiqueta: no se toca.
                {"public_id": "proy_prod/imagenes/ajena", "created_at": "2026-01-01T00:00:00Z", "secure_url": "https://x/ajena.jpg"},
                {"public_id": "proy_test/imagenes/vieja2", "created_at": "2026-01-02T00:00:00Z", "secure_url": "https://x/vieja2.jpg"},
            ],
        },
    ]

    def resources_by_tag(tag, **options):
        calls["resources_by_tag"].append((tag, options))
        return pages[len(calls["resources_by_tag"]) - 1]

    monkeypatch.setattr(cloudinary.api, "resources_by_tag", resources_by_tag)
    monkeypatch.setattr(cloudinary.api, "delete_resources", lambda ids, **o: calls["delete_resources"].append((ids, o)))
    monkeypatch.setattr(cloudinary.uploader, "remove_tag", lambda tag, ids: calls["remove_tag"].append((tag, ids)))
    monkeypatch.setattr(cloudinary_module, "_ensure_configured", lambda: None)
    return calls


async def test_lista_las_pendientes_viejas_de_este_entorno_en_todas_las_paginas(sdk):
    settings = make_settings(TEST_CLOUDINARY_FOLDER_NAME="proy_test")
    pending = await CloudinaryService.list_pending_uploads(settings, datetime(2026, 6, 1, tzinfo=timezone.utc))
    assert pending == [
        {"public_id": "proy_test/imagenes/vieja", "url": "https://x/vieja.jpg"},
        {"public_id": "proy_test/imagenes/vieja2", "url": "https://x/vieja2.jpg"},
    ]
    assert [tag for tag, _ in sdk["resources_by_tag"]] == ["pendiente", "pendiente"]
    assert sdk["resources_by_tag"][1][1]["next_cursor"] == "pagina-2"


async def test_borra_de_a_100_y_quita_la_etiqueta(sdk):
    ids = [f"proy_test/imagenes/{i}" for i in range(250)]
    await CloudinaryService.delete_images(ids)
    assert [len(batch) for batch, _ in sdk["delete_resources"]] == [100, 100, 50]
    await CloudinaryService.remove_pending_tag(ids[:2])
    assert sdk["remove_tag"] == [("pendiente", ids[:2])]
    # Sin ids no llama a la API.
    await CloudinaryService.delete_images([])
    await CloudinaryService.remove_pending_tag([])
    assert len(sdk["delete_resources"]) == 3 and len(sdk["remove_tag"]) == 1


# ---------- Service y endpoint (base de desarrollo, transacción revertida) ----------

async def test_borra_las_huerfanas_y_conserva_las_que_usa_un_registro(client, admin, user, cloudinary):
    en_uso = uploaded_image_url()
    response = await client.post(
        "/api/v1/pagos/registrar",
        json={
            "user_id": str(user.id),
            "plan_id": str(PLAN_PRO_ID),
            "metodo": "qr",
            "comprobante_url": en_uso,
            "idempotency_key": uuid4().hex,
        },
        headers=auth_header(admin),
    )
    assert response.status_code == 201
    huerfana = uploaded_image_url()
    cloudinary.pending = [
        {"public_id": "huerfana", "url": huerfana},
        # Su confirmación falló: sigue pendiente aunque el pago la usa.
        {"public_id": "en-uso", "url": en_uso},
    ]

    response = await client.post(URL, headers=auth_header(admin))
    assert response.status_code == 200
    assert response.json() == {"eliminadas": 1, "conservadas": 1}
    assert cloudinary.deleted_ids == ["huerfana"]
    assert cloudinary.untagged_ids == ["en-uso"]


async def test_sin_pendientes_no_hace_nada(client, superadmin, cloudinary):
    response = await client.post(URL, headers=auth_header(superadmin))
    assert response.json() == {"eliminadas": 0, "conservadas": 0}
    assert cloudinary.deleted_ids == [] and cloudinary.untagged_ids == []


async def test_solo_los_admins_la_disparan(client, user, cloudinary):
    response = await client.post(URL, headers=auth_header(user))
    assert response.status_code == 403
    assert (await client.post(URL)).status_code == 401
    assert cloudinary.deleted_ids == []


def test_el_job_arranca_en_un_proceso_limpio():
    code = (
        "import jobs.limpiar_imagenes_huerfanas; "
        "from sqlalchemy.orm import configure_mappers; configure_mappers()"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr[-2000:]
