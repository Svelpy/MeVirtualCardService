"""Ronda 1 (AGENTS.md §25): schemas planos Create, Update, Response, ResponseAudit, Ref y Public."""

from datetime import time
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domains.auth.schemas import ChangePassword, UserLogin, UserRegister
from app.domains.pago.schemas import PagoCreate
from app.domains.plan.schemas import PlanUpdate
from app.domains.tarjeta.schemas import TarjetaCreate, TarjetaUpdate
from app.domains.tarjeta_certificacion.schemas import TarjetaCertificacionCreate
from app.domains.tarjeta_contacto.schemas import TarjetaContactoCreate
from app.domains.tarjeta_educacion.schemas import TarjetaEducacionCreate
from app.domains.tarjeta_theme.schemas import TarjetaThemeUpdate
from app.domains.tarjeta_ubicacion.schemas import TarjetaUbicacionCreate
from app.domains.ubicacion_horario.schemas import UbicacionHorarioCreate, UbicacionHorarioResponse
from app.domains.usuario.schemas import UsuarioCreate, UsuarioResponse, UsuarioUpdateMe
from app.domains.vitrina.schemas import VitrinaCreate
from app.domains.vitrina.schemas import VitrinaUpdate
from app.domains.vitrina_item.schemas import VitrinaItemCreate
from app.shared.enums import Role


TARJETA_MINIMA = {"slug": "ana-perez", "rubro": "Pediatría", "nombres": "Ana"}
VITRINA_ID = "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b"


# ---------- Update: campos omitidos, null y exclude_unset ----------

def test_update_vacio_no_modifica_nada():
    assert TarjetaUpdate().model_dump(exclude_unset=True) == {}


def test_update_rechaza_null_en_columna_no_nullable():
    with pytest.raises(ValidationError, match="no puede ser null"):
        PlanUpdate(nombre=None)
    with pytest.raises(ValidationError, match="no puede ser null"):
        TarjetaThemeUpdate(color_fondo=None)


def test_update_acepta_null_en_columna_nullable_para_borrarla():
    data = TarjetaUpdate(prefijo=None, cover_url=None)
    assert data.model_dump(exclude_unset=True) == {"prefijo": None, "cover_url": None}


def test_update_conserva_false():
    data = VitrinaUpdate(mostrar_precios=False)
    assert data.model_dump(exclude_unset=True) == {"mostrar_precios": False}


def test_los_schemas_rechazan_campos_desconocidos():
    with pytest.raises(ValidationError, match="extra"):
        TarjetaCreate(**TARJETA_MINIMA, id=VITRINA_ID)  # el id lo genera el sistema
    with pytest.raises(ValidationError, match="extra"):
        TarjetaUpdate(is_public=True)  # el estado cambia solo con acciones
    with pytest.raises(ValidationError, match="extra"):
        PlanUpdate(codigo="gold")  # Filas fijas: el código no se edita
    with pytest.raises(ValidationError, match="extra"):
        UsuarioUpdateMe(rol="admin")  # nadie cambia su propio rol


# ---------- Normalización y formato ----------

def test_normaliza_email_moneda_y_color():
    assert UsuarioCreate(email=" Ana@Example.COM ", password="ClaveSegura123").email == "ana@example.com"
    assert VitrinaCreate(moneda=" usd ").moneda == "USD"
    assert TarjetaThemeUpdate(color_fondo="ff00aa").color_fondo == "#FF00AA"


def test_el_rol_por_defecto_es_user():
    assert UsuarioCreate(email="ana@example.com", password="ClaveSegura123").rol is Role.USER


def test_slug_con_formato_y_longitud_de_la_columna():
    with pytest.raises(ValidationError):
        TarjetaCreate(**{**TARJETA_MINIMA, "slug": "Ana Pérez"})
    with pytest.raises(ValidationError):
        TarjetaCreate(**{**TARJETA_MINIMA, "slug": "ab"})


def test_las_urls_de_imagen_exigen_https():
    with pytest.raises(ValidationError, match="HTTPS"):
        TarjetaCreate(**TARJETA_MINIMA, cover_url="http://example.com/portada.jpg")


def test_no_convierte_tipos_en_silencio():
    with pytest.raises(ValidationError):
        VitrinaCreate(mostrar_precios="true")
    with pytest.raises(ValidationError):
        PlanUpdate(duracion_dias="365")


def test_precio_respeta_numeric_12_2():
    assert PlanUpdate(precio="80.50").precio == Decimal("80.50")
    with pytest.raises(ValidationError):
        PlanUpdate(precio="80.505")
    with pytest.raises(ValidationError):
        PlanUpdate(precio=-1)


# ---------- Contraseñas ----------

def test_registro_aplica_la_politica_de_contrasenas():
    with pytest.raises(ValidationError, match="al menos 8"):
        UserRegister(email="ana@example.com", password="corta")


def test_login_no_aplica_la_politica_para_responder_401_y_no_422():
    assert UserLogin(email="ana@example.com", password="corta").password == "corta"
    with pytest.raises(ValidationError):
        ChangePassword(current_password="corta", new_password="corta")


def test_la_respuesta_de_usuario_nunca_expone_el_hash():
    assert "password_hash" not in UsuarioResponse.model_fields


# ---------- Reglas entre campos ----------

def test_contacto_valida_el_valor_segun_su_tipo():
    assert TarjetaContactoCreate(tipo="email", valor=" Ana@Example.com ").valor == "ana@example.com"
    assert TarjetaContactoCreate(tipo="phone", valor="+59170000001").valor == "+59170000001"
    with pytest.raises(ValidationError):
        TarjetaContactoCreate(tipo="email", valor="no-es-email")
    with pytest.raises(ValidationError):
        TarjetaContactoCreate(tipo="website", valor="http://example.com")


def test_solo_un_telefono_puede_ser_whatsapp():
    with pytest.raises(ValidationError, match="WhatsApp"):
        TarjetaContactoCreate(tipo="email", valor="ana@example.com", is_wpp=True)


def test_educacion_y_certificacion_validan_sus_fechas():
    with pytest.raises(ValidationError, match="anterior"):
        TarjetaEducacionCreate(institucion="UMSA", fecha_inicio="2020-01-01", fecha_fin="2019-01-01")
    with pytest.raises(ValidationError, match="actual"):
        TarjetaEducacionCreate(institucion="UMSA", is_actual=True, fecha_fin="2019-01-01")
    with pytest.raises(ValidationError, match="no expira"):
        TarjetaCertificacionCreate(nombre="ACLS", no_expira=True, fecha_expiracion="2030-01-01")


def test_latitud_y_longitud_van_juntas():
    with pytest.raises(ValidationError, match="juntas"):
        TarjetaUbicacionCreate(direccion="Av. Arce", lat="-16.5")


def test_horario_sin_cruzar_la_medianoche_y_en_formato_hh_mm():
    with pytest.raises(ValidationError, match="posterior"):
        UbicacionHorarioCreate(dia_semana=1, hora_inicio="18:00", hora_fin="02:00")
    with pytest.raises(ValidationError):
        UbicacionHorarioCreate(dia_semana=8, hora_inicio="08:00", hora_fin="12:00")
    response = UbicacionHorarioResponse.model_validate(
        UbicacionHorarioResponse.model_config["json_schema_extra"]["example"]
    )
    assert response.hora_inicio == time(8, 30)
    assert response.model_dump(mode="json")["hora_inicio"] == "08:30"


def test_precio_anterior_requiere_precio_y_ser_mayor():
    with pytest.raises(ValidationError, match="precio anterior"):
        VitrinaItemCreate(titulo="Consulta", precio_anterior="10.00")
    with pytest.raises(ValidationError, match="precio anterior"):
        VitrinaItemCreate(titulo="Consulta", precio="10.00", precio_anterior="5.00")
    item = VitrinaItemCreate(titulo="Consulta", precio="5.00", precio_anterior="10.00")
    assert item.precio_anterior == Decimal("10.00")


def test_pago_acepta_un_monto_opcional_pero_no_la_moneda_ni_el_periodo():
    base = {
        "user_id": VITRINA_ID,
        "plan_id": VITRINA_ID,
        "metodo": "qr",
        "idempotency_key": "pago-1",
    }
    assert PagoCreate(**base).monto is None  # sin monto: el precio del plan
    assert PagoCreate(**base, monto="60.5").monto == Decimal("60.5")
    with pytest.raises(ValidationError, match="mayor o igual a cero"):
        PagoCreate(**base, monto="-1")
    for extra in ({"moneda": "USD"}, {"periodo_fin": "2027-01-01T00:00:00Z"}):
        with pytest.raises(ValidationError, match="extra"):
            PagoCreate(**base, **extra)
