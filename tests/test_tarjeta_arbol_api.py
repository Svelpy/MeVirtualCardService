"""
Segunda vuelta (§25): la tarjeta con todo su árbol, sus extensiones, la
auditoría de las hijas embebidas y la lectura pública, con datos reales de
todo el árbol en la base de desarrollo (transacción revertida).
"""

from uuid import uuid4

from app.shared.enums import ClaveSeccion
from app.domains.tarjeta_theme.schemas import THEME_PRESETS
from app.shared.enums import PresetTheme
from tests.conftest import auth_header, create_usuario, uploaded_image_url


TARJETAS = "/api/v1/tarjetas"


def _arbol(**overrides) -> dict:
    return {
        "slug": f"dra-ana-{uuid4().hex[:6]}",
        "rubro": "Pediatría",
        "nombres": "Ana María",
        "theme": {"preset": "oscuro"},
        "seo": {"meta_title": "Dra. Ana", "robots_index": False},
        "vitrina": {
            "moneda": "usd",
            "categorias": [{"nombre": "Consultas", "orden": 1}, {"nombre": "Talleres", "orden": 0, "is_visible": False}],
        },
        "contactos": [
            {"tipo": "phone", "valor": "70000002", "orden": 1},
            {"tipo": "phone", "valor": "70000001", "is_primary": True, "is_wpp": True, "orden": 0},
            {"tipo": "email", "valor": "ana@clinica.example.com", "orden": 2, "is_visible": False},
        ],
        "ubicaciones": [
            {
                "direccion": "Av. Arce 100",
                "orden": 0,
                "horarios": [
                    {"dia_semana": 2, "hora_inicio": "08:00", "hora_fin": "12:00"},
                    {"dia_semana": 1, "hora_inicio": "14:00", "hora_fin": "18:00"},
                    {"dia_semana": 1, "hora_inicio": "08:00", "hora_fin": "12:00"},
                ],
            },
            {"direccion": "Calle 21 de Calacoto", "orden": 1, "horarios": []},
        ],
        "redes": [{"red": "instagram", "url": "https://instagram.com/draana"}],
        "educaciones": [{"institucion": "UMSA", "titulo": "Medicina"}],
        "certificaciones": [{"nombre": "Pediatría avanzada", "no_expira": True}],
        "faqs": [{"pregunta": "¿Atiende sábados?", "respuesta": "Sí, por la mañana."}],
        **overrides,
    }


async def _crear(client, usuario, **overrides) -> dict:
    response = await client.post(f"{TARJETAS}/", json=_arbol(**overrides), headers=auth_header(usuario))
    assert response.status_code == 201, response.text
    return response.json()


def _secciones(detail: dict, **cambios) -> list[dict]:
    return [
        {"id": s["id"], "titulo": s["titulo"], "is_visible": s["is_visible"], "orden": s["orden"], **cambios}
        for s in detail["secciones"]
    ]


# ---------- Crear con el árbol y leer el detalle ----------

async def test_crear_con_todo_el_arbol_y_leer_su_detalle(client, user):
    creada = await _crear(client, user)
    detail = (await client.get(f"{TARJETAS}/{creada['id']}", headers=auth_header(user))).json()
    assert detail == creada  # POST responde lo mismo que GET /{id}

    assert detail["user"]["email"] == user.email and "password_hash" not in detail["user"]
    assert [s["clave"] for s in detail["secciones"]] == [c.value for c in ClaveSeccion]
    # Las listas salen en su orden, no en el de llegada.
    assert [c["valor"] for c in detail["contactos"]] == ["70000001", "70000002", "ana@clinica.example.com"]
    ubicacion = detail["ubicaciones"][0]
    assert [(h["dia_semana"], h["hora_inicio"]) for h in ubicacion["horarios"]] == [
        (1, "08:00"),
        (1, "14:00"),
        (2, "08:00"),
    ]
    assert detail["ubicaciones"][1]["horarios"] == []
    assert [len(detail[k]) for k in ("redes", "educaciones", "certificaciones", "faqs")] == [1, 1, 1, 1]
    # Las extensiones no embebidas tienen sus propias rutas (§20).
    assert "theme" not in detail and "vitrina" not in detail


async def test_las_extensiones_se_crean_con_lo_recibido(client, user):
    tarjeta = await _crear(client, user)
    headers = auth_header(user)
    theme = (await client.get(f"/api/v1/tarjeta-themes/{tarjeta['id']}", headers=headers)).json()
    assert (theme["preset"], theme["tipografia"]) == ("oscuro", 1)  # con solo el preset
    oscuro = THEME_PRESETS[PresetTheme.OSCURO]
    assert {field: theme[field] for field in oscuro} == oscuro  # todos sus valores, también los no color
    seo = (await client.get(f"/api/v1/tarjeta-seos/{tarjeta['id']}", headers=headers)).json()
    assert (seo["meta_title"], seo["robots_index"]) == ("Dra. Ana", False)
    vitrina = (await client.get(f"/api/v1/vitrinas/{tarjeta['id']}", headers=headers)).json()
    assert vitrina["moneda"] == "USD"
    assert [c["nombre"] for c in vitrina["categorias"]] == ["Talleres", "Consultas"]


async def test_crear_valida_las_reglas_de_las_listas(client, user):
    principal = {"tipo": "phone", "valor": "70000001", "is_primary": True}
    for overrides in (
        {"contactos": [principal, {**principal, "valor": "70000002"}]},
        {"redes": [{"red": "x", "url": "https://x.com/a"}, {"red": "x", "url": "https://x.com/b"}]},
        {"faqs": [{"pregunta": "¿?", "respuesta": "Sí"}] * 31},
        {"secciones": []},  # las crea el service
        {"ubicaciones": [{"direccion": "A", "horarios": [
            {"dia_semana": 1, "hora_inicio": "08:00", "hora_fin": "12:00"},
            {"dia_semana": 1, "hora_inicio": "11:00", "hora_fin": "13:00"},
        ]}]},
    ):
        response = await client.post(f"{TARJETAS}/", json=_arbol(**overrides), headers=auth_header(user))
        assert response.status_code == 422, overrides


# ---------- Editar el árbol ----------

async def test_editar_sincroniza_cada_lista_como_estado_final(client, user):
    tarjeta = await _crear(client, user)
    headers = auth_header(user)
    principal, secundario, email = tarjeta["contactos"]
    faq = tarjeta["faqs"][0]

    response = await client.patch(
        f"{TARJETAS}/{tarjeta['id']}",
        json={
            # Intercambia el contacto principal entre dos filas existentes y elimina el email.
            "contactos": [
                {"id": principal["id"], "tipo": "phone", "valor": principal["valor"], "orden": 1},
                {"id": secundario["id"], "tipo": "phone", "valor": secundario["valor"], "is_primary": True, "orden": 0},
            ],
            # Actualiza la FAQ existente y agrega una nueva.
            "faqs": [
                {"id": faq["id"], "pregunta": faq["pregunta"], "respuesta": "Solo con cita."},
                {"pregunta": "¿Hay estacionamiento?", "respuesta": "Sí."},
            ],
            "redes": [],  # [] elimina todas
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    assert [(c["id"], c["is_primary"]) for c in detail["contactos"]] == [(secundario["id"], True), (principal["id"], False)]
    assert email["id"] not in {c["id"] for c in detail["contactos"]}
    assert [f["respuesta"] for f in detail["faqs"]] == ["Solo con cita.", "Sí."]
    assert detail["faqs"][0]["id"] == faq["id"]
    assert detail["redes"] == []
    # Lo que no se envió no se toca.
    assert len(detail["educaciones"]) == 1 and len(detail["ubicaciones"]) == 2


async def test_editar_ubicaciones_y_sus_horarios(client, admin, user):
    tarjeta = await _crear(client, user)
    primera, segunda = tarjeta["ubicaciones"]
    tramo = primera["horarios"][0]
    response = await client.patch(
        f"{TARJETAS}/{tarjeta['id']}",
        json={
            "ubicaciones": [
                {
                    "id": primera["id"],
                    "direccion": primera["direccion"],
                    "horarios": [
                        {"id": tramo["id"], "dia_semana": 1, "hora_inicio": "09:00", "hora_fin": "12:00"},
                        {"dia_semana": 5, "hora_inicio": "08:00", "hora_fin": "10:00"},
                    ],
                },
                {"direccion": "Nueva sucursal", "horarios": [{"dia_semana": 6, "hora_inicio": "09:00", "hora_fin": "13:00"}]},
            ]
        },
        headers=auth_header(user),
    )
    assert response.status_code == 200, response.text
    ubicaciones = response.json()["ubicaciones"]
    assert [u["direccion"] for u in ubicaciones] == ["Av. Arce 100", "Nueva sucursal"]
    assert [(h["id"] == tramo["id"], h["hora_inicio"]) for h in ubicaciones[0]["horarios"]] == [(True, "09:00"), (False, "08:00")]
    assert ubicaciones[1]["horarios"][0]["dia_semana"] == 6

    # La ubicación eliminada arrastra sus horarios (cascada §19), visible en la auditoría.
    audit = await client.get(f"/api/v1/tarjeta-ubicaciones/{segunda['id']}/audit", headers=auth_header(admin))
    assert audit.json()["is_deleted"] is True
    for horario in primera["horarios"][1:]:
        audit = await client.get(f"/api/v1/ubicacion-horarios/{horario['id']}/audit", headers=auth_header(admin))
        assert audit.json()["is_deleted"] is True


async def test_horarios_ausentes_no_se_tocan(client, user):
    tarjeta = await _crear(client, user)
    primera = tarjeta["ubicaciones"][0]
    response = await client.patch(
        f"{TARJETAS}/{tarjeta['id']}",
        json={"ubicaciones": [{"id": primera["id"], "direccion": "Av. Arce 200"}]},
        headers=auth_header(user),
    )
    ubicacion = response.json()["ubicaciones"][0]
    assert ubicacion["direccion"] == "Av. Arce 200"
    assert [h["id"] for h in ubicacion["horarios"]] == [h["id"] for h in primera["horarios"]]


async def test_las_secciones_se_editan_las_8_a_la_vez(client, user):
    tarjeta = await _crear(client, user)
    secciones = _secciones(tarjeta)
    secciones[0] |= {"titulo": "Conóceme", "orden": 7}
    secciones[7] |= {"is_visible": False, "orden": 0}
    response = await client.patch(f"{TARJETAS}/{tarjeta['id']}", json={"secciones": secciones}, headers=auth_header(user))
    assert response.status_code == 200
    detail = response.json()
    assert [s["clave"] for s in detail["secciones"]][0] == "faq"
    assert detail["secciones"][-1]["titulo"] == "Conóceme"

    response = await client.patch(f"{TARJETAS}/{tarjeta['id']}", json={"secciones": secciones[:7]}, headers=auth_header(user))
    assert response.status_code == 422


async def test_un_id_de_otra_tarjeta_responde_422_y_no_aplica_nada(client, db_session, user):
    otro = await create_usuario(db_session, "otro@test.example.com")
    ajena = await _crear(client, otro)
    propia = await _crear(client, user)
    faq_ajena = ajena["faqs"][0]
    response = await client.patch(
        f"{TARJETAS}/{propia['id']}",
        json={"rubro": "Otro rubro", "faqs": [{"id": faq_ajena["id"], "pregunta": "¿Mía?", "respuesta": "No."}]},
        headers=auth_header(user),
    )
    assert response.status_code == 422
    assert response.json()["details"] == {"faqs": [faq_ajena["id"]]}
    detail = (await client.get(f"{TARJETAS}/{propia['id']}", headers=auth_header(user))).json()
    assert detail["rubro"] == "Pediatría"

    secciones = _secciones(propia)
    secciones[0]["id"] = ajena["secciones"][0]["id"]
    response = await client.patch(f"{TARJETAS}/{propia['id']}", json={"secciones": secciones}, headers=auth_header(user))
    assert response.status_code == 422


async def test_el_listado_trae_el_usuario(client, admin, user):
    await _crear(client, user)
    body = (await client.get(f"{TARJETAS}/?user_id={user.id}", headers=auth_header(admin))).json()
    assert body["data"][0]["user"] == {"id": str(user.id), "email": user.email}
    assert "contactos" not in body["data"][0]  # un listado no lleva colecciones


# ---------- Lectura pública ----------

async def test_la_lectura_publica_muestra_solo_lo_visible(client, user):
    tarjeta = await _crear(client, user)
    secciones = _secciones(tarjeta)
    secciones[2]["is_visible"] = False  # vitrina
    await client.patch(f"{TARJETAS}/{tarjeta['id']}", json={"secciones": secciones}, headers=auth_header(user))
    assert (await client.get(f"{TARJETAS}/public/{tarjeta['slug']}")).status_code == 404  # sin publicar

    await client.post(f"{TARJETAS}/{tarjeta['id']}/publicar", headers=auth_header(user))
    response = await client.get(f"{TARJETAS}/public/{tarjeta['slug']}")
    assert response.status_code == 200
    public = response.json()
    assert "created_by" not in public and "is_public" not in public and "user_id" not in public
    assert [s["clave"] for s in public["secciones"]] == [c.value for c in ClaveSeccion if c != ClaveSeccion.VITRINA]
    assert [c["valor"] for c in public["contactos"]] == ["70000001", "70000002"]  # el email está oculto
    assert [c["nombre"] for c in public["vitrina"]["categorias"]] == ["Consultas"]  # Talleres está oculta
    assert public["theme"]["color_fondo"] == THEME_PRESETS[PresetTheme.OSCURO]["color_fondo"]
    assert len(public["ubicaciones"][0]["horarios"]) == 3

    # Por id, como la pide el QR.
    assert (await client.get(f"{TARJETAS}/public/id/{tarjeta['id']}")).json() == public


async def test_me_trae_la_tarjeta_completa_como_la_ve_su_dueno(client, db_session, user):
    me = (await client.get("/api/v1/usuarios/me", headers=auth_header(user))).json()
    assert me["tarjeta"] is None and me["plan"]["id"] == str(user.plan_id)  # todavía no la creó

    tarjeta = await _crear(client, user)
    vitrina_url = f"/api/v1/vitrinas/{tarjeta['id']}"
    talleres = (await client.get(vitrina_url, headers=auth_header(user))).json()["categorias"][0]
    items = [
        {"titulo": "Taller", "categoria_id": talleres["id"], "precio": "100", "imagenes": [{"url": uploaded_image_url()}]},
        {"titulo": "Oculto", "is_visible": False, "precio": "50"},
    ]
    response = await client.patch(
        vitrina_url, json={"mostrar_precios": False, "items": items}, headers=auth_header(user)
    )
    assert response.status_code == 200, response.text
    otro = await create_usuario(db_session, "otro@test.example.com")
    await _crear(client, otro)

    response = await client.get("/api/v1/usuarios/me", headers=auth_header(user))
    assert response.status_code == 200
    mia = response.json()["tarjeta"]
    assert mia["id"] == tarjeta["id"] and mia["user_id"] == str(user.id)
    assert mia["theme"]["preset"] == "oscuro" and mia["seo"]["meta_title"] == "Dra. Ana"
    assert len(mia["secciones"]) == 8
    # Lo oculto también viene: el dueño decide qué editar.
    assert {c["valor"] for c in mia["contactos"]} == {"70000001", "70000002", "ana@clinica.example.com"}
    assert [c["nombre"] for c in mia["vitrina"]["categorias"]] == ["Talleres", "Consultas"]
    assert {i["titulo"]: i["precio"] for i in mia["vitrina"]["items"]} == {"Taller": "100.00", "Oculto": "50.00"}
    taller = next(i for i in mia["vitrina"]["items"] if i["titulo"] == "Taller")
    assert taller["categoria"]["nombre"] == "Talleres" and len(taller["imagenes"]) == 1
    assert len(mia["ubicaciones"][0]["horarios"]) == 3
    # Las hijas vienen igual que en el detalle de la tarjeta.
    detail = (await client.get(f"{TARJETAS}/{tarjeta['id']}", headers=auth_header(user))).json()
    for field in ("secciones", "contactos", "ubicaciones", "redes", "educaciones", "certificaciones", "faqs"):
        assert mia[field] == detail[field], field
    assert (await client.get(f"{TARJETAS}/me", headers=auth_header(user))).status_code in (404, 422)

    await client.delete(f"{TARJETAS}/{tarjeta['id']}", headers=auth_header(user))
    assert (await client.get("/api/v1/usuarios/me", headers=auth_header(user))).json()["tarjeta"] is None


async def test_completa_trae_lo_mismo_que_me_y_aplica_el_alcance(client, db_session, admin, user):
    tarjeta = await _crear(client, user)
    url = f"{TARJETAS}/{tarjeta['id']}/completa"
    mia = (await client.get("/api/v1/usuarios/me", headers=auth_header(user))).json()["tarjeta"]

    propia = await client.get(url, headers=auth_header(user))
    assert propia.status_code == 200
    assert propia.json() == mia
    # Un admin la ve igual que su dueño, sin los datos del usuario.
    completa = (await client.get(url, headers=auth_header(admin))).json()
    assert completa == mia and "user" not in completa

    # Fuera del alcance, inexistente o eliminada: 404.
    otro = await create_usuario(db_session, "otro@test.example.com")
    assert (await client.get(url, headers=auth_header(otro))).status_code == 404
    assert (await client.get(f"{TARJETAS}/{uuid4()}/completa", headers=auth_header(admin))).status_code == 404
    await client.delete(f"{TARJETAS}/{tarjeta['id']}", headers=auth_header(user))
    assert (await client.get(url, headers=auth_header(admin))).status_code == 404


async def test_la_lectura_publica_exige_dueno_activo_y_plan_vigente(client, db_session, admin):
    vencido = await create_usuario(db_session, "vence@test.example.com", plan_vence_at_days=1)
    tarjeta = await _crear(client, vencido)
    await client.post(f"{TARJETAS}/{tarjeta['id']}/publicar", headers=auth_header(vencido))
    assert (await client.get(f"{TARJETAS}/public/{tarjeta['slug']}")).status_code == 200

    vencido.plan_vence_at = vencido.created_at  # ya venció
    await db_session.commit()
    assert (await client.get(f"{TARJETAS}/public/{tarjeta['slug']}")).status_code == 404


async def test_los_items_publicos_de_la_vitrina(client, user):
    tarjeta = await _crear(client, user)
    url = f"/api/v1/vitrinas/{tarjeta['id']}"
    talleres, consultas = (await client.get(url, headers=auth_header(user))).json()["categorias"]
    items = [
        {"titulo": "Consulta", "categoria_id": consultas["id"], "orden": 1, "precio": "250"},
        {"titulo": "Sin categoría", "orden": 0},
        {"titulo": "Oculto", "is_visible": False},
        {"titulo": "Taller", "categoria_id": talleres["id"]},  # categoría oculta
    ]
    response = await client.patch(url, json={"items": items}, headers=auth_header(user))
    assert response.status_code == 200, response.text

    await client.post(f"{TARJETAS}/{tarjeta['id']}/publicar", headers=auth_header(user))
    vitrina = (await client.get(f"{TARJETAS}/public/{tarjeta['slug']}")).json()["vitrina"]
    assert [item["titulo"] for item in vitrina["items"]] == ["Sin categoría", "Consulta"]
    assert "is_visible" not in vitrina["items"][0]
    assert vitrina["items"][1]["precio"] == "250.00"

    # Si la vitrina oculta precios, los items salen sin ellos.
    await client.patch(url, json={"mostrar_precios": False}, headers=auth_header(user))
    vitrina = (await client.get(f"{TARJETAS}/public/{tarjeta['slug']}")).json()["vitrina"]
    assert vitrina["items"][1]["precio"] is None


# ---------- Extensiones 1:1 ----------

async def test_theme_editar_un_color_lo_personaliza_y_aplicar_preset_lo_restaura(client, user):
    tarjeta = await _crear(client, user)
    url = f"/api/v1/tarjeta-themes/{tarjeta['id']}"
    response = await client.patch(url, json={"color_primario": "ff0000"}, headers=auth_header(user))
    assert (response.json()["preset"], response.json()["color_primario"]) == (None, "#FF0000")
    response = await client.patch(url, json={"tipografia": 2}, headers=auth_header(user))
    assert response.json()["preset"] is None  # la tipografía no cambia el preset
    # Aplicar un preset nuevo copia todos sus valores; editar la forma de los íconos lo personaliza.
    response = await client.post(f"{url}/aplicar-preset", json={"preset": "energia"}, headers=auth_header(user))
    energia = THEME_PRESETS[PresetTheme.ENERGIA]
    assert {field: response.json()[field] for field in energia} == energia
    response = await client.patch(url, json={"icono_forma": "circulo"}, headers=auth_header(user))
    assert response.json()["preset"] is None

    response = await client.post(f"{url}/aplicar-preset", json={"preset": "salud"}, headers=auth_header(user))
    body = response.json()
    assert body["preset"] == "salud" and body["tipografia"] == 2
    assert body["color_primario"] == THEME_PRESETS[PresetTheme.SALUD]["color_primario"]
    for payload in ({"color_fondo": "rojo"}, {"preset": "claro"}, {"overlay_opacidad": 101}):
        assert (await client.patch(url, json=payload, headers=auth_header(user))).status_code == 422, payload


async def test_seo_reemplazar_la_imagen_borra_la_anterior(client, user, cloudinary):
    tarjeta = await _crear(client, user)
    url = f"/api/v1/tarjeta-seos/{tarjeta['id']}"
    primera, segunda = uploaded_image_url(), uploaded_image_url()
    await client.patch(url, json={"og_image_url": primera}, headers=auth_header(user))
    response = await client.patch(url, json={"og_image_url": segunda, "meta_title": None}, headers=auth_header(user))
    assert (response.json()["og_image_url"], response.json()["meta_title"]) == (segunda, None)
    assert cloudinary.deleted == [primera]
    assert cloudinary.confirmed[segunda] == f"tarjetas/{tarjeta['id']}"


async def test_vitrina_una_categoria_con_items_no_se_elimina(client, user):
    tarjeta = await _crear(client, user)
    url = f"/api/v1/vitrinas/{tarjeta['id']}"
    talleres, consultas = (await client.get(url, headers=auth_header(user))).json()["categorias"]
    response = await client.patch(
        url, json={"items": [{"titulo": "Consulta", "categoria_id": consultas["id"]}]}, headers=auth_header(user)
    )
    assert response.status_code == 200, response.text
    response = await client.patch(url, json={"categorias": [{"id": talleres["id"], "nombre": "Talleres"}]}, headers=auth_header(user))
    assert response.status_code == 409
    assert response.json()["details"] == {"categorias": [consultas["id"]]}

    # Intercambiar los nombres de dos categorías no choca con el índice único.
    response = await client.patch(
        url,
        json={
            "mostrar_precios": False,
            "categorias": [
                {"id": talleres["id"], "nombre": "Consultas"},
                {"id": consultas["id"], "nombre": "Talleres"},
                {"nombre": "Cursos"},
            ],
        },
        headers=auth_header(user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mostrar_precios"] is False
    assert {c["id"]: c["nombre"] for c in body["categorias"]}[talleres["id"]] == "Consultas"
    assert len(body["categorias"]) == 3


async def test_las_extensiones_aplican_el_alcance_de_su_tarjeta(client, db_session, user):
    otro = await create_usuario(db_session, "otro@test.example.com")
    ajena = await _crear(client, otro)
    for method, url, body in (
        ("GET", f"/api/v1/tarjeta-themes/{ajena['id']}", None),
        ("PATCH", f"/api/v1/tarjeta-themes/{ajena['id']}", {"tipografia": 2}),
        ("POST", f"/api/v1/tarjeta-themes/{ajena['id']}/aplicar-preset", {"preset": "claro"}),
        ("GET", f"/api/v1/tarjeta-seos/{ajena['id']}", None),
        ("PATCH", f"/api/v1/tarjeta-seos/{ajena['id']}", {"meta_title": "Mío"}),
        ("GET", f"/api/v1/vitrinas/{ajena['id']}", None),
        ("PATCH", f"/api/v1/vitrinas/{ajena['id']}", {"mostrar_precios": False}),
    ):
        response = await client.request(method, url, json=body, headers=auth_header(user))
        assert response.status_code == 404, (method, url)


# ---------- Item de vitrina con sus imágenes ----------

async def test_item_con_imagenes_detalle_e_intercambio_de_la_principal(client, user, cloudinary):
    tarjeta = await _crear(client, user)
    url = f"/api/v1/vitrinas/{tarjeta['id']}"
    categoria = (await client.get(url, headers=auth_header(user))).json()["categorias"][1]
    a, b = uploaded_image_url(), uploaded_image_url()
    item = {
        "titulo": "Consulta",
        "categoria_id": categoria["id"],
        "imagenes": [{"url": b, "orden": 1}, {"url": a, "orden": 0, "alt": "Consultorio"}],
    }
    response = await client.patch(url, json={"items": [item]}, headers=auth_header(user))
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["categoria"]["nombre"] == "Consultas"
    assert [i["url"] for i in item["imagenes"]] == [a, b]
    assert cloudinary.confirmed[a] == f"tarjetas/{tarjeta['id']}/vitrina"

    imagen_a, imagen_b = item["imagenes"]
    c = uploaded_image_url()
    response = await client.patch(
        url,
        json={
            "items": [
                {
                    "id": item["id"],
                    "titulo": "Consulta",
                    "categoria_id": categoria["id"],
                    "imagenes": [
                        {"id": imagen_b["id"], "url": b, "orden": 0},  # pasa a ser la principal
                        {"id": imagen_a["id"], "url": c, "orden": 1},  # cambia su imagen
                    ],
                }
            ]
        },
        headers=auth_header(user),
    )
    assert response.status_code == 200, response.text
    imagenes = response.json()["items"][0]["imagenes"]
    assert [(i["id"], i["url"]) for i in imagenes] == [(imagen_b["id"], b), (imagen_a["id"], c)]
    assert cloudinary.deleted == [a]

    # imagenes ausente no las toca.
    response = await client.patch(url, json={"items": [{"id": item["id"], "titulo": "Otra"}]}, headers=auth_header(user))
    assert len(response.json()["items"][0]["imagenes"]) == 2


async def test_item_dos_imagenes_principales_responden_422(client, user):
    tarjeta = await _crear(client, user)
    imagenes = [{"url": uploaded_image_url(), "orden": 0}, {"url": uploaded_image_url(), "orden": 0}]
    response = await client.patch(
        f"/api/v1/vitrinas/{tarjeta['id']}",
        json={"items": [{"titulo": "Consulta", "imagenes": imagenes}]},
        headers=auth_header(user),
    )
    assert response.status_code == 422


# ---------- Auditoría de las hijas embebidas ----------

async def test_las_hijas_embebidas_solo_exponen_su_auditoria(client, admin, user):
    tarjeta = await _crear(client, user)
    rutas = {
        "tarjeta-secciones": tarjeta["secciones"][0]["id"],
        "tarjeta-contactos": tarjeta["contactos"][0]["id"],
        "tarjeta-ubicaciones": tarjeta["ubicaciones"][0]["id"],
        "ubicacion-horarios": tarjeta["ubicaciones"][0]["horarios"][0]["id"],
        "tarjeta-redes": tarjeta["redes"][0]["id"],
        "tarjeta-educaciones": tarjeta["educaciones"][0]["id"],
        "tarjeta-certificaciones": tarjeta["certificaciones"][0]["id"],
        "tarjeta-faqs": tarjeta["faqs"][0]["id"],
    }
    for prefix, child_id in rutas.items():
        url = f"/api/v1/{prefix}/{child_id}/audit"
        response = await client.get(url, headers=auth_header(admin))
        assert response.status_code == 200, url
        assert response.json()["created_by"] == str(user.id)
        assert (await client.get(url, headers=auth_header(user))).status_code == 403, url  # el user no audita
        assert (await client.get(f"/api/v1/{prefix}/{child_id}", headers=auth_header(admin))).status_code in (404, 405)
    assert (await client.get(f"/api/v1/tarjeta-faqs/{uuid4()}/audit", headers=auth_header(admin))).status_code == 404

    # Siguen auditables después de eliminar la tarjeta.
    await client.delete(f"{TARJETAS}/{tarjeta['id']}", headers=auth_header(user))
    response = await client.get(f"/api/v1/tarjeta-faqs/{rutas['tarjeta-faqs']}/audit", headers=auth_header(admin))
    assert response.status_code == 200 and response.json()["is_deleted"] is True
