"""Ronda 2 (AGENTS.md §25): ResponseItemList, ResponseDetail, CreateNested, UpdateNested y NestedItem."""

import typing
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from app.domains.pago.schemas import PagoResponse, PagoResponseDetail, PagoResponseItemList
from app.domains.tarjeta.schemas import (
    TarjetaCreateNested,
    TarjetaResponse,
    TarjetaResponseDetail,
    TarjetaResponseItemList,
    TarjetaUpdateNested,
)
from app.domains.tarjeta_ubicacion.schemas import (
    TarjetaUbicacionCreateNested,
    TarjetaUbicacionNestedItem,
    TarjetaUbicacionResponseDetail,
)
from app.domains.usuario.schemas import UsuarioResponse, UsuarioResponseDetail, UsuarioResponseItemList
from app.domains.vitrina.schemas import VitrinaCreateNested, VitrinaResponseDetail, VitrinaUpdateNested
from app.domains.vitrina_item.schemas import (
    VitrinaItemCreateNested,
    VitrinaItemNestedItem,
    VitrinaItemResponse,
    VitrinaItemResponseDetail,
)


TARJETA_MINIMA = {"slug": "ana-perez", "rubro": "Pediatría", "nombres": "Ana"}
VITRINA_ID = "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b"


def _secciones(n: int = 8) -> list[dict]:
    return [{"id": str(uuid4()), "orden": orden} for orden in range(n)]


def _list_fields(schema: type[BaseModel]) -> set[str]:
    return {
        name
        for name, field in schema.model_fields.items()
        if typing.get_origin(field.annotation) is list
        or any(typing.get_origin(arg) is list for arg in typing.get_args(field.annotation))
    }


# ---------- Estructura (§20) ----------

@pytest.mark.parametrize(
    ("response", "derived"),
    [
        (UsuarioResponse, UsuarioResponseItemList),
        (UsuarioResponse, UsuarioResponseDetail),
        (PagoResponse, PagoResponseItemList),
        (PagoResponse, PagoResponseDetail),
        (TarjetaResponse, TarjetaResponseItemList),
        (TarjetaResponse, TarjetaResponseDetail),
        (VitrinaItemResponse, VitrinaItemResponseDetail),
    ],
)
def test_las_salidas_con_relaciones_heredan_la_plana(response, derived):
    # Por eso el paso de la primera a la segunda vuelta es compatible (§25).
    assert issubclass(derived, response)


@pytest.mark.parametrize(
    "item_list", [UsuarioResponseItemList, PagoResponseItemList, TarjetaResponseItemList]
)
def test_un_listado_nunca_contiene_colecciones(item_list):
    assert _list_fields(item_list) == set()


@pytest.mark.parametrize(
    ("update_nested", "detail"),
    [
        (TarjetaUpdateNested, TarjetaResponseDetail),
        (VitrinaUpdateNested, VitrinaResponseDetail),
        (VitrinaItemNestedItem, VitrinaItemResponseDetail),
        (TarjetaUbicacionNestedItem, TarjetaUbicacionResponseDetail),
    ],
)
def test_el_detalle_embebe_el_mismo_arbol_que_acepta_su_update(update_nested, detail):
    assert _list_fields(detail) == _list_fields(update_nested)


def test_las_extensiones_no_embebidas_solo_estan_en_create_nested():
    for extension in ("theme", "seo", "vitrina"):
        assert extension in TarjetaCreateNested.model_fields
        assert extension not in TarjetaUpdateNested.model_fields
        assert extension not in TarjetaResponseDetail.model_fields


# ---------- CreateNested ----------

def test_create_nested_minimo_deja_listas_vacias_y_extensiones_por_defecto():
    data = TarjetaCreateNested(**TARJETA_MINIMA)
    assert data.contactos == [] and data.faqs == []
    assert data.theme is None and data.vitrina is None
    assert "secciones" not in TarjetaCreateNested.model_fields  # las crea el service


def test_create_nested_respeta_el_maximo_de_cada_lista():
    contacto = {"tipo": "phone", "valor": "70000001"}
    with pytest.raises(ValidationError, match="at most 10|10"):
        TarjetaCreateNested(**TARJETA_MINIMA, contactos=[contacto] * 11)


def test_un_contacto_principal_por_tipo_y_una_cuenta_por_red():
    principal = {"tipo": "phone", "valor": "70000001", "is_primary": True}
    with pytest.raises(ValidationError, match="principal"):
        TarjetaCreateNested(**TARJETA_MINIMA, contactos=[principal, {**principal, "valor": "70000002"}])
    red = {"red": "instagram", "url": "https://instagram.com/ana"}
    with pytest.raises(ValidationError, match="una cuenta por red"):
        TarjetaCreateNested(**TARJETA_MINIMA, redes=[red, red])


def test_horarios_que_se_solapan_se_rechazan_y_los_contiguos_no():
    manana = {"dia_semana": 1, "hora_inicio": "08:00", "hora_fin": "12:00"}
    tarde = {"dia_semana": 1, "hora_inicio": "12:00", "hora_fin": "18:00"}
    assert len(TarjetaUbicacionCreateNested(direccion="Av. Arce", horarios=[manana, tarde]).horarios) == 2
    with pytest.raises(ValidationError, match="solapan"):
        TarjetaUbicacionCreateNested(direccion="Av. Arce", horarios=[manana, {**tarde, "hora_inicio": "11:00"}])


def test_categorias_con_nombre_unico_e_imagen_principal_unica():
    with pytest.raises(ValidationError, match="mismo nombre"):
        VitrinaCreateNested(categorias=[{"nombre": "Consultas"}, {"nombre": "Consultas"}])
    imagen = {"url": "https://res.cloudinary.com/demo/image/upload/v1/a.jpg", "orden": 0}
    with pytest.raises(ValidationError, match="principal"):
        VitrinaItemCreateNested(titulo="Consulta", imagenes=[imagen, imagen])
    with pytest.raises(ValidationError, match="sin categoría"):
        VitrinaCreateNested(items=[{"titulo": "Consulta", "categoria_id": VITRINA_ID}])


# ---------- UpdateNested ----------

def test_lista_ausente_no_se_toca_y_lista_vacia_elimina_todo():
    assert "faqs" not in TarjetaUpdateNested().model_dump(exclude_unset=True)
    assert TarjetaUpdateNested(faqs=[]).model_dump(exclude_unset=True) == {"faqs": []}
    assert TarjetaUpdateNested(faqs=None).faqs is None


def test_elemento_sin_id_se_crea_y_con_id_se_actualiza():
    item_id = uuid4()
    data = TarjetaUpdateNested(
        faqs=[{"pregunta": "¿Nueva?", "respuesta": "Sí"}, {"id": str(item_id), "pregunta": "¿Vieja?", "respuesta": "Sí"}]
    )
    assert [faq.id for faq in data.faqs] == [None, item_id]


def test_ids_repetidos_en_una_lista_se_rechazan():
    item_id = str(uuid4())
    faq = {"id": item_id, "pregunta": "¿Atiende?", "respuesta": "Sí"}
    with pytest.raises(ValidationError, match="repetidos"):
        TarjetaUpdateNested(faqs=[faq, faq])
    horario = {"id": item_id, "dia_semana": 1, "hora_inicio": "08:00", "hora_fin": "09:00"}
    with pytest.raises(ValidationError, match="repetidos"):
        TarjetaUbicacionNestedItem(direccion="Av. Arce", horarios=[horario, {**horario, "dia_semana": 2}])


def test_las_secciones_son_siempre_las_8_con_su_id():
    assert len(TarjetaUpdateNested(secciones=_secciones()).secciones) == 8
    with pytest.raises(ValidationError):
        TarjetaUpdateNested(secciones=_secciones(7))
    with pytest.raises(ValidationError):
        TarjetaUpdateNested(secciones=[{"orden": orden} for orden in range(8)])  # sin id
    with pytest.raises(ValidationError, match="extra"):
        TarjetaUpdateNested(secciones=[{**s, "clave": "faq"} for s in _secciones()])  # la clave no se edita


def test_horarios_ausentes_en_una_ubicacion_no_se_tocan():
    ubicacion = TarjetaUbicacionNestedItem(id=str(uuid4()), direccion="Av. Arce")
    assert ubicacion.horarios is None
    assert "horarios" not in ubicacion.model_dump(exclude_unset=True)


def test_update_nested_valida_las_mismas_reglas_que_la_creacion():
    principal = {"tipo": "phone", "valor": "70000001", "is_primary": True}
    with pytest.raises(ValidationError, match="principal"):
        TarjetaUpdateNested(contactos=[principal, {**principal, "valor": "70000002"}])
    with pytest.raises(ValidationError, match="mismo nombre"):
        VitrinaUpdateNested(categorias=[{"nombre": "A"}, {"nombre": "A"}])
