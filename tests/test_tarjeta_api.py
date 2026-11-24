"""API de tarjeta (Raíz, primera vuelta) contra la base de desarrollo, dentro de una transacción revertida."""

from datetime import time
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.domains.tarjeta_faq.models import TarjetaFaq
from app.domains.tarjeta_seccion.models import TarjetaSeccion
from app.domains.tarjeta_seo.models import TarjetaSeo
from app.domains.tarjeta_theme.models import TarjetaTheme
from app.domains.tarjeta_theme.schemas import COLOR_FIELDS, PRESET_FIELDS, THEME_PRESETS, TarjetaThemeCreate
from app.domains.tarjeta_ubicacion.models import TarjetaUbicacion
from app.domains.ubicacion_horario.models import UbicacionHorario
from app.domains.vitrina.models import Vitrina
from app.shared.enums import ClaveSeccion, FormaIcono, PosicionFab, PresetTheme
from app.shared.services.validators import validator_hex_color
from tests.conftest import auth_header, create_usuario, uploaded_image_url


BASE = "/api/v1/tarjetas"


def _tarjeta(**overrides) -> dict:
    return {"slug": f"ana-{uuid4().hex[:8]}", "rubro": "Pediatría", "nombres": "Ana", **overrides}


async def _crear(client, usuario, **overrides) -> dict:
    response = await client.post(f"{BASE}/", json=_tarjeta(**overrides), headers=auth_header(usuario))
    assert response.status_code == 201, response.text
    return response.json()


# ---------- Presets ----------

def test_hay_un_preset_por_cada_valor_del_enum():
    assert list(THEME_PRESETS) == list(PresetTheme)
    assert [preset.value for preset in PresetTheme] == [
        "claro", "oscuro", "elegante", "salud", "corporativo", "calido", "natural", "belleza", "creativo", "energia"
    ]


@pytest.mark.parametrize("preset", list(PresetTheme))
def test_cada_preset_define_todos_sus_campos_con_valores_validos(preset):
    valores = THEME_PRESETS[preset]
    assert list(valores) == list(PRESET_FIELDS)
    assert set(COLOR_FIELDS) <= set(PRESET_FIELDS) and "tipografia" not in valores
    assert all(validator_hex_color(valores[field]) == valores[field] for field in COLOR_FIELDS)
    assert 0 <= valores["overlay_opacidad"] <= 100
    assert isinstance(valores["icono_forma"], FormaIcono) and isinstance(valores["fab_posicion"], PosicionFab)


def test_el_theme_se_crea_solo_con_el_preset():
    assert TarjetaThemeCreate(preset="energia").preset is PresetTheme.ENERGIA
    with pytest.raises(ValidationError):
        TarjetaThemeCreate(preset="claro", tipografia=3)  # la tipografía no se elige al crear
    with pytest.raises(ValidationError):
        TarjetaThemeCreate(preset="neon")


# ---------- Crear ----------

async def test_el_dueno_la_crea_despublicada_con_theme_seo_vitrina_y_secciones(client, db_session, user):
    tarjeta = await _crear(client, user)
    assert tarjeta["user_id"] == str(user.id)
    assert tarjeta["is_public"] is False and tarjeta["published_at"] is None

    tarjeta_id = tarjeta["id"]
    theme = (await db_session.execute(select(TarjetaTheme).where(TarjetaTheme.id == tarjeta_id))).scalar_one()
    assert theme.preset == PresetTheme.CLARO and theme.color_fondo == THEME_PRESETS[PresetTheme.CLARO]["color_fondo"]
    assert (await db_session.execute(select(TarjetaSeo).where(TarjetaSeo.id == tarjeta_id))).scalar_one()
    assert (await db_session.execute(select(Vitrina).where(Vitrina.id == tarjeta_id))).scalar_one().moneda == "BOB"
    secciones = (
        await db_session.execute(
            select(TarjetaSeccion).where(TarjetaSeccion.tarjeta_id == tarjeta_id).order_by(TarjetaSeccion.orden)
        )
    ).scalars().all()
    assert [s.clave for s in secciones] == list(ClaveSeccion)


async def test_una_tarjeta_por_usuario_y_slug_unico_responden_409(client, db_session, user):
    tarjeta = await _crear(client, user)
    response = await client.post(f"{BASE}/", json=_tarjeta(), headers=auth_header(user))
    assert response.status_code == 409

    otro = await create_usuario(db_session, "otro@test.example.com")
    response = await client.post(f"{BASE}/", json=_tarjeta(slug=tarjeta["slug"]), headers=auth_header(otro))
    assert response.status_code == 409
    assert response.json()["details"] == {"slug": "Ya está en uso."}


async def test_los_admins_no_crean_tarjetas(client, admin, superadmin):
    for actor in (admin, superadmin):
        assert (await client.post(f"{BASE}/", json=_tarjeta(), headers=auth_header(actor))).status_code == 403


async def test_datos_invalidos_responden_422(client, user):
    for body in (
        _tarjeta(slug="Con Espacios"),
        _tarjeta(slug="ab"),
        _tarjeta(is_public=True),  # publicar es una acción
        _tarjeta(user_id=str(uuid4())),  # el dueño sale del actor
        _tarjeta(nombres="Ana123"),
        _tarjeta(cargo=""),
        _tarjeta(nombre_empresa_posicion="centro"),
        {"slug": "ana-perez", "nombres": "Ana"},  # falta rubro
    ):
        response = await client.post(f"{BASE}/", json=body, headers=auth_header(user))
        assert response.status_code == 422, body


# ---------- Imágenes ----------

async def test_las_imagenes_se_validan_se_confirman_y_las_reemplazadas_se_borran(client, user, cloudinary):
    foto = uploaded_image_url()
    tarjeta = await _crear(client, user, profile_url=foto)
    assert cloudinary.confirmed == {foto: f"tarjetas/{tarjeta['id']}"}

    nueva = uploaded_image_url()
    response = await client.patch(f"{BASE}/{tarjeta['id']}", json={"profile_url": nueva}, headers=auth_header(user))
    assert response.status_code == 200
    assert response.json()["profile_url"] == nueva
    assert cloudinary.deleted == [foto]

    response = await client.patch(f"{BASE}/{tarjeta['id']}", json={"profile_url": None}, headers=auth_header(user))
    assert response.json()["profile_url"] is None
    assert cloudinary.deleted == [foto, nueva]


async def test_una_imagen_ajena_o_repetida_responde_422(client, user):
    response = await client.post(
        f"{BASE}/", json=_tarjeta(profile_url="https://example.com/foto.jpg"), headers=auth_header(user)
    )
    assert response.status_code == 422
    misma = uploaded_image_url()
    response = await client.post(f"{BASE}/", json=_tarjeta(profile_url=misma, cover_url=misma), headers=auth_header(user))
    assert response.status_code == 422
    assert response.json()["details"] == {"cover_url": "La misma imagen no puede usarse en dos campos."}


# ---------- Alcance (404) y permisos ----------

async def test_un_usuario_no_ve_ni_modifica_la_tarjeta_de_otro(client, db_session, user):
    otro = await create_usuario(db_session, "otro@test.example.com")
    ajena = await _crear(client, otro)
    propia = await _crear(client, user)
    headers = auth_header(user)

    for method, url, body in (
        ("GET", f"{BASE}/{ajena['id']}", None),
        ("PATCH", f"{BASE}/{ajena['id']}", {"rubro": "Otro"}),
        ("DELETE", f"{BASE}/{ajena['id']}", None),
        ("POST", f"{BASE}/{ajena['id']}/publicar", None),
        ("POST", f"{BASE}/{ajena['id']}/despublicar", None),
    ):
        response = await client.request(method, url, json=body, headers=headers)
        assert response.status_code == 404, (method, url)

    listado = (await client.get(f"{BASE}/", headers=headers)).json()
    assert [t["id"] for t in listado["data"]] == [propia["id"]]
    # Ni filtrando por el otro dueño.
    assert (await client.get(f"{BASE}/?user_id={otro.id}", headers=headers)).json()["total"] == 0


async def test_slug_disponible_es_publico_y_reconoce_el_slug_propio(client, db_session, user):
    url = f"{BASE}/public/slug-disponible"
    tarjeta = await _crear(client, user)

    libre = (await client.get(f"{url}/libre-{uuid4().hex[:8]}")).json()
    assert libre["disponible"] is True
    assert (await client.get(f"{url}/{tarjeta['slug']}")).json() == {"slug": tarjeta["slug"], "disponible": False}
    # Para su dueño, su slug actual cuenta como disponible; para otro usuario, no.
    propio = await client.get(f"{url}/{tarjeta['slug']}", headers=auth_header(user))
    assert propio.json()["disponible"] is True
    otro = await create_usuario(db_session, "otro@test.example.com")
    assert (await client.get(f"{url}/{tarjeta['slug']}", headers=auth_header(otro))).json()["disponible"] is False

    for invalido in ("ab", "Con-Mayusculas", "-guion", "doble--guion", "a" * 81):
        assert (await client.get(f"{url}/{invalido}")).status_code == 422, invalido

    # Al eliminar la tarjeta, su slug queda libre.
    await client.delete(f"{BASE}/{tarjeta['id']}", headers=auth_header(user))
    assert (await client.get(f"{url}/{tarjeta['slug']}")).json()["disponible"] is True


async def test_el_user_no_audita_su_tarjeta(client, user):
    tarjeta = await _crear(client, user)
    assert (await client.get(f"{BASE}/{tarjeta['id']}/audit", headers=auth_header(user))).status_code == 403


async def test_los_admins_moderan_cualquier_tarjeta(client, db_session, admin, user):
    tarjeta = await _crear(client, user)
    headers = auth_header(admin)
    assert (await client.get(f"{BASE}/?user_id={user.id}", headers=headers)).json()["total"] == 1
    response = await client.patch(f"{BASE}/{tarjeta['id']}", json={"rubro": "Pediatría infantil"}, headers=headers)
    assert response.status_code == 200
    audit = (await client.get(f"{BASE}/{tarjeta['id']}/audit", headers=headers)).json()
    assert audit["updated_by"] == str(admin.id)
    assert (await client.delete(f"{BASE}/{tarjeta['id']}", headers=headers)).status_code == 204


async def test_sin_token_responde_401(client):
    assert (await client.get(f"{BASE}/")).status_code == 401


async def test_tarjeta_inexistente_responde_404(client, admin):
    assert (await client.get(f"{BASE}/{uuid4()}", headers=auth_header(admin))).status_code == 404


# ---------- Editar ----------

async def test_editar_cambia_solo_lo_enviado_y_libera_el_slug(client, db_session, user):
    tarjeta = await _crear(client, user, cargo="Pediatra")
    viejo = tarjeta["slug"]
    response = await client.patch(
        f"{BASE}/{tarjeta['id']}", json={"slug": "dra-ana-nueva", "apellidos": None}, headers=auth_header(user)
    )
    assert response.status_code == 200
    assert (response.json()["slug"], response.json()["cargo"]) == ("dra-ana-nueva", "Pediatra")

    otro = await create_usuario(db_session, "otro@test.example.com")
    assert (await client.post(f"{BASE}/", json=_tarjeta(slug=viejo), headers=auth_header(otro))).status_code == 201


async def test_editar_con_datos_invalidos_responde_422(client, user):
    tarjeta = await _crear(client, user)
    for body in ({"slug": None}, {"rubro": None}, {"is_public": True}, {"published_at": None}):
        response = await client.patch(f"{BASE}/{tarjeta['id']}", json=body, headers=auth_header(user))
        assert response.status_code == 422, body


# ---------- Publicar ----------

async def test_publicar_exige_email_verificado_y_plan_vigente(client, db_session):
    sin_verificar = await create_usuario(db_session, "sinverificar@test.example.com", verified=False)
    vencido = await create_usuario(db_session, "vencido@test.example.com", plan_vence_at_days=-1)
    for usuario, mensaje in ((sin_verificar, "Verifica tu email"), (vencido, "El plan venció")):
        tarjeta = await _crear(client, usuario)
        response = await client.post(f"{BASE}/{tarjeta['id']}/publicar", headers=auth_header(usuario))
        assert response.status_code == 409
        assert response.json()["message"].startswith(mensaje)


async def test_publicar_y_despublicar(client, user, admin):
    tarjeta = await _crear(client, user)
    response = await client.post(f"{BASE}/{tarjeta['id']}/publicar", headers=auth_header(user))
    assert response.status_code == 200
    assert response.json()["is_public"] is True and response.json()["published_at"] is not None

    # El admin la despublica (moderación).
    response = await client.post(f"{BASE}/{tarjeta['id']}/despublicar", headers=auth_header(admin))
    assert response.json()["is_public"] is False
    assert (await client.get(f"{BASE}/?is_public=true", headers=auth_header(user))).json()["total"] == 0


# ---------- Eliminar ----------

async def test_eliminar_cae_en_cascada_sobre_todo_el_arbol(client, db_session, user):
    tarjeta = await _crear(client, user)
    tarjeta_id = tarjeta["id"]
    faq = TarjetaFaq(tarjeta_id=tarjeta_id, pregunta="¿Atiende?", respuesta="Sí")
    ubicacion = TarjetaUbicacion(tarjeta_id=tarjeta_id, direccion="Av. Arce")
    db_session.add_all([faq, ubicacion])
    await db_session.flush()
    horario = UbicacionHorario(ubicacion_id=ubicacion.id, dia_semana=1, hora_inicio=time(8), hora_fin=time(12))
    db_session.add(horario)
    await db_session.commit()

    assert (await client.delete(f"{BASE}/{tarjeta_id}", headers=auth_header(user))).status_code == 204
    assert (await client.get(f"{BASE}/{tarjeta_id}", headers=auth_header(user))).status_code == 404

    for model, condition in (
        (TarjetaTheme, TarjetaTheme.id == tarjeta_id),
        (Vitrina, Vitrina.id == tarjeta_id),
        (TarjetaSeccion, TarjetaSeccion.tarjeta_id == tarjeta_id),
        (TarjetaFaq, TarjetaFaq.id == faq.id),
        (UbicacionHorario, UbicacionHorario.id == horario.id),
    ):
        flags = (
            await db_session.execute(
                select(model.is_deleted, model.deleted_by).where(condition).execution_options(populate_existing=True)
            )
        ).all()
        assert flags and all(row == (True, user.id) for row in flags), model.__name__

    # Libera la tarjeta del usuario: puede crear otra con el mismo slug.
    assert (await client.post(f"{BASE}/", json=_tarjeta(slug=tarjeta["slug"]), headers=auth_header(user))).status_code == 201
