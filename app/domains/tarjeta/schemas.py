from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.domains.plan.schemas import PLAN_RESPONSE_EXAMPLE
from app.domains.tarjeta_certificacion.schemas import (
    TARJETA_CERTIFICACION_CREATE_EXAMPLES,
    TARJETA_CERTIFICACION_MAX,
    TARJETA_CERTIFICACION_NESTED_EXAMPLES,
    TARJETA_CERTIFICACION_PUBLIC_EXAMPLES,
    TARJETA_CERTIFICACION_RESPONSE_EXAMPLES,
    TarjetaCertificacionCreate,
    TarjetaCertificacionNestedItem,
    TarjetaCertificacionPublic,
    TarjetaCertificacionResponse,
)
from app.domains.tarjeta_contacto.schemas import (
    TARJETA_CONTACTO_CREATE_EXAMPLES,
    TARJETA_CONTACTO_MAX,
    TARJETA_CONTACTO_NESTED_EXAMPLES,
    TARJETA_CONTACTO_PUBLIC_EXAMPLES,
    TARJETA_CONTACTO_RESPONSE_EXAMPLES,
    TarjetaContactoCreate,
    TarjetaContactoNestedItem,
    TarjetaContactoPublic,
    TarjetaContactoResponse,
    ensure_one_primary_per_tipo,
)
from app.domains.tarjeta_educacion.schemas import (
    TARJETA_EDUCACION_CREATE_EXAMPLES,
    TARJETA_EDUCACION_MAX,
    TARJETA_EDUCACION_NESTED_EXAMPLES,
    TARJETA_EDUCACION_PUBLIC_EXAMPLES,
    TARJETA_EDUCACION_RESPONSE_EXAMPLES,
    TarjetaEducacionCreate,
    TarjetaEducacionNestedItem,
    TarjetaEducacionPublic,
    TarjetaEducacionResponse,
)
from app.domains.tarjeta_faq.schemas import (
    TARJETA_FAQ_CREATE_EXAMPLES,
    TARJETA_FAQ_MAX,
    TARJETA_FAQ_NESTED_EXAMPLES,
    TARJETA_FAQ_PUBLIC_EXAMPLES,
    TARJETA_FAQ_RESPONSE_EXAMPLES,
    TarjetaFaqCreate,
    TarjetaFaqNestedItem,
    TarjetaFaqPublic,
    TarjetaFaqResponse,
)
from app.domains.tarjeta_seccion.schemas import (
    TARJETA_SECCION_COUNT,
    TARJETA_SECCION_NESTED_EXAMPLES,
    TARJETA_SECCION_PUBLIC_EXAMPLES,
    TARJETA_SECCION_RESPONSE_EXAMPLES,
    TarjetaSeccionNestedItem,
    TarjetaSeccionPublic,
    TarjetaSeccionResponse,
)
from app.domains.tarjeta_seo.schemas import (
    TARJETA_SEO_PUBLIC_EXAMPLE,
    TARJETA_SEO_RESPONSE_EXAMPLE,
    TarjetaSeoCreate,
    TarjetaSeoPublic,
    TarjetaSeoResponse,
)
from app.domains.tarjeta_social.schemas import (
    TARJETA_SOCIAL_CREATE_EXAMPLES,
    TARJETA_SOCIAL_MAX,
    TARJETA_SOCIAL_NESTED_EXAMPLES,
    TARJETA_SOCIAL_PUBLIC_EXAMPLES,
    TARJETA_SOCIAL_RESPONSE_EXAMPLES,
    TarjetaSocialCreate,
    TarjetaSocialNestedItem,
    TarjetaSocialPublic,
    TarjetaSocialResponse,
    ensure_unique_red,
)
from app.domains.tarjeta_theme.schemas import (
    TARJETA_THEME_CREATE_EXAMPLE,
    TARJETA_THEME_PUBLIC_EXAMPLE,
    TARJETA_THEME_RESPONSE_EXAMPLE,
    TarjetaThemeCreate,
    TarjetaThemePublic,
    TarjetaThemeResponse,
)
from app.domains.tarjeta_ubicacion.schemas import (
    TARJETA_UBICACION_CREATE_NESTED_EXAMPLES,
    TARJETA_UBICACION_MAX,
    TARJETA_UBICACION_NESTED_EXAMPLES,
    TARJETA_UBICACION_PUBLIC_EXAMPLES,
    TARJETA_UBICACION_RESPONSE_DETAIL_EXAMPLES,
    TarjetaUbicacionCreateNested,
    TarjetaUbicacionNestedItem,
    TarjetaUbicacionPublic,
    TarjetaUbicacionResponseDetail,
)
from app.domains.usuario.schemas import (
    USUARIO_REF_EXAMPLE,
    USUARIO_REF_EXAMPLES,
    USUARIO_RESPONSE_EXAMPLE,
    UsuarioRef,
    UsuarioResponse,
    UsuarioResponseDetail,
)
from app.domains.vitrina.schemas import (
    VITRINA_CREATE_NESTED_EXAMPLE,
    VITRINA_PUBLIC_EXAMPLE,
    VITRINA_RESPONSE_DETAIL_EXAMPLE,
    VitrinaCreateNested,
    VitrinaPublic,
    VitrinaResponseDetail,
)
from app.shared.enums import PosicionNombreEmpresa
from app.shared.schemas.base import AUDIT_EXAMPLE, AuditMixin, SchemaBase, reject_null
from app.shared.services.validators import (
    validator_https_url,
    validator_name,
    validator_non_empty_text,
    validator_slug,
    validator_unique_ids,
)


TARJETA_ID = "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7b"

_CAMPOS_EXAMPLE = {
    "slug": "dra-ana-perez",
    "rubro": "Pediatría",
    "prefijo": "Dra.",
    "nombres": "Ana María",
    "apellidos": "Pérez Quispe",
    "cargo": "Médica pediatra",
    "nombre_empresa": "Clínica Los Andes",
    "acerca_de_mi": "Pediatra con 8 años de experiencia en atención infantil.",
    "profile_url": "https://res.cloudinary.com/demo/image/upload/v1/perfil.jpg",
    "photo_usuario_url": "https://res.cloudinary.com/demo/image/upload/v1/foto.jpg",
    "logo_empresa_url": "https://res.cloudinary.com/demo/image/upload/v1/logo.png",
    "nombre_empresa_posicion": "derecha",
    "cover_url": "https://res.cloudinary.com/demo/image/upload/v1/portada.jpg",
    "qr_pago_url": "https://res.cloudinary.com/demo/image/upload/v1/qr-pago.png",
}
TARJETA_CREATE_EXAMPLE = _CAMPOS_EXAMPLE
TARJETA_RESPONSE_EXAMPLE = {
    "id": TARJETA_ID,
    "user_id": "8f14e45f-ceea-467a-9575-6b3f0c1a2b3c",
    **_CAMPOS_EXAMPLE,
    "is_public": True,
    "published_at": "2026-01-20T10:00:00Z",
    "created_at": "2026-01-15T14:30:00Z",
    "updated_at": "2026-02-01T09:00:00Z",
}

_TEXTO_OPCIONAL_FIELDS = ("prefijo", "cargo", "nombre_empresa", "acerca_de_mi")
_URL_FIELDS = ("profile_url", "photo_usuario_url", "logo_empresa_url", "cover_url", "qr_pago_url")


# =================================
# Ronda 1: schemas planos
# =================================

class TarjetaCreate(SchemaBase):
    """
    user_id sale del actor autenticado. is_public y published_at cambian solo
    con las acciones publicar / despublicar. Las URLs de imagen son las que
    devolvió POST /imagenes/uploads; el service comprueba su origen.
    """

    slug: str = Field(min_length=3, max_length=80)
    rubro: str = Field(max_length=150)
    prefijo: str | None = Field(default=None, max_length=30)
    nombres: str = Field(max_length=150)
    apellidos: str | None = Field(default=None, max_length=150)
    cargo: str | None = Field(default=None, max_length=150)
    nombre_empresa: str | None = Field(default=None, max_length=200)
    acerca_de_mi: str | None = None
    profile_url: str | None = None
    photo_usuario_url: str | None = None
    logo_empresa_url: str | None = None
    nombre_empresa_posicion: PosicionNombreEmpresa = PosicionNombreEmpresa.DERECHA
    cover_url: str | None = None
    qr_pago_url: str | None = None

    @field_validator("slug", mode="before")
    @classmethod
    def validate_slug(cls, value: object) -> str:
        return validator_slug(value)

    @field_validator("rubro", mode="before")
    @classmethod
    def validate_rubro(cls, value: object) -> str:
        return validator_non_empty_text(value)

    @field_validator("nombres", mode="before")
    @classmethod
    def validate_nombres(cls, value: object) -> str:
        return validator_name(value)

    @field_validator("apellidos", mode="before")
    @classmethod
    def validate_apellidos(cls, value: object) -> str | None:
        return None if value is None else validator_name(value)

    @field_validator(*_TEXTO_OPCIONAL_FIELDS, mode="before")
    @classmethod
    def validate_texto_opcional(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator(*_URL_FIELDS, mode="before")
    @classmethod
    def validate_url(cls, value: object) -> str | None:
        return None if value is None else validator_https_url(value)

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_CREATE_EXAMPLE})


TARJETA_REGISTRO_EXAMPLE = {
    "slug": "dra-ana-perez",
    "rubro": "Pediatría",
    "prefijo": "Dra.",
    "nombres": "Ana María",
    "apellidos": "Pérez Quispe",
    "cargo": "Médica pediatra",
    "theme": {"preset": "salud"},
}


class TarjetaRegistro(SchemaBase):
    """
    La tarjeta que se crea con el registro público (POST /auth/register), con
    lo mínimo para empezar. Sin imágenes: subirlas exige sesión. El resto de la
    tarjeta (empresa, imágenes, seo, vitrina, contactos...) se completa después
    con sus rutas de edición.
    """

    slug: str = Field(min_length=3, max_length=80)
    rubro: str = Field(max_length=150)
    prefijo: str | None = Field(default=None, max_length=30)
    nombres: str = Field(max_length=150)
    apellidos: str | None = Field(default=None, max_length=150)
    cargo: str | None = Field(default=None, max_length=150)
    theme: TarjetaThemeCreate | None = None  # sin theme: preset claro

    @field_validator("slug", mode="before")
    @classmethod
    def validate_slug(cls, value: object) -> str:
        return validator_slug(value)

    @field_validator("rubro", mode="before")
    @classmethod
    def validate_rubro(cls, value: object) -> str:
        return validator_non_empty_text(value)

    @field_validator("nombres", mode="before")
    @classmethod
    def validate_nombres(cls, value: object) -> str:
        return validator_name(value)

    @field_validator("apellidos", mode="before")
    @classmethod
    def validate_apellidos(cls, value: object) -> str | None:
        return None if value is None else validator_name(value)

    @field_validator("prefijo", "cargo", mode="before")
    @classmethod
    def validate_texto_opcional(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_REGISTRO_EXAMPLE})


class TarjetaUpdate(SchemaBase):
    """Cambiar el slug libera el anterior; el QR sigue funcionando porque apunta al id."""

    slug: str = Field(default=None, min_length=3, max_length=80)
    rubro: str = Field(default=None, max_length=150)
    prefijo: str | None = Field(default=None, max_length=30)
    nombres: str = Field(default=None, max_length=150)
    apellidos: str | None = Field(default=None, max_length=150)
    cargo: str | None = Field(default=None, max_length=150)
    nombre_empresa: str | None = Field(default=None, max_length=200)
    acerca_de_mi: str | None = Field(default=None)
    profile_url: str | None = Field(default=None)
    photo_usuario_url: str | None = Field(default=None)
    logo_empresa_url: str | None = Field(default=None)
    nombre_empresa_posicion: PosicionNombreEmpresa = Field(default=None)
    cover_url: str | None = Field(default=None)
    qr_pago_url: str | None = Field(default=None)

    @field_validator("slug", mode="before")
    @classmethod
    def validate_slug(cls, value: object) -> str:
        return validator_slug(reject_null(value))

    @field_validator("rubro", mode="before")
    @classmethod
    def validate_rubro(cls, value: object) -> str:
        return validator_non_empty_text(reject_null(value))

    @field_validator("nombres", mode="before")
    @classmethod
    def validate_nombres(cls, value: object) -> str:
        return validator_name(reject_null(value))

    @field_validator("apellidos", mode="before")
    @classmethod
    def validate_apellidos(cls, value: object) -> str | None:
        return None if value is None else validator_name(value)

    @field_validator(*_TEXTO_OPCIONAL_FIELDS, mode="before")
    @classmethod
    def validate_texto_opcional(cls, value: object) -> str | None:
        return None if value is None else validator_non_empty_text(value)

    @field_validator(*_URL_FIELDS, mode="before")
    @classmethod
    def validate_url(cls, value: object) -> str | None:
        return None if value is None else validator_https_url(value)

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_CREATE_EXAMPLE})


class TarjetaResponse(SchemaBase):
    id: UUID
    user_id: UUID
    slug: str
    rubro: str
    prefijo: str | None
    nombres: str
    apellidos: str | None
    cargo: str | None
    nombre_empresa: str | None
    acerca_de_mi: str | None
    profile_url: str | None
    photo_usuario_url: str | None
    logo_empresa_url: str | None
    nombre_empresa_posicion: PosicionNombreEmpresa
    cover_url: str | None
    qr_pago_url: str | None
    is_public: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_RESPONSE_EXAMPLE})


class TarjetaResponseAudit(AuditMixin, TarjetaResponse):
    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_RESPONSE_EXAMPLE, **AUDIT_EXAMPLE}})


class TarjetaPublic(SchemaBase):
    """
    Tarjeta publicada para un visitante anónimo: todo su árbol, sin auditoría y
    solo con las filas visibles.
    """

    id: UUID
    slug: str
    rubro: str
    prefijo: str | None
    nombres: str
    apellidos: str | None
    cargo: str | None
    nombre_empresa: str | None
    acerca_de_mi: str | None
    profile_url: str | None
    photo_usuario_url: str | None
    logo_empresa_url: str | None
    nombre_empresa_posicion: PosicionNombreEmpresa
    cover_url: str | None
    qr_pago_url: str | None
    theme: TarjetaThemePublic
    seo: TarjetaSeoPublic
    secciones: list[TarjetaSeccionPublic]
    contactos: list[TarjetaContactoPublic]
    ubicaciones: list[TarjetaUbicacionPublic]
    redes: list[TarjetaSocialPublic]
    educaciones: list[TarjetaEducacionPublic]
    certificaciones: list[TarjetaCertificacionPublic]
    faqs: list[TarjetaFaqPublic]
    vitrina: VitrinaPublic

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": TARJETA_ID,
                **_CAMPOS_EXAMPLE,
                "theme": TARJETA_THEME_PUBLIC_EXAMPLE,
                "seo": TARJETA_SEO_PUBLIC_EXAMPLE,
                "secciones": TARJETA_SECCION_PUBLIC_EXAMPLES,
                "contactos": TARJETA_CONTACTO_PUBLIC_EXAMPLES,
                "ubicaciones": TARJETA_UBICACION_PUBLIC_EXAMPLES,
                "redes": TARJETA_SOCIAL_PUBLIC_EXAMPLES,
                "educaciones": TARJETA_EDUCACION_PUBLIC_EXAMPLES,
                "certificaciones": TARJETA_CERTIFICACION_PUBLIC_EXAMPLES,
                "faqs": TARJETA_FAQ_PUBLIC_EXAMPLES,
                "vitrina": VITRINA_PUBLIC_EXAMPLE,
            }
        }
    )


class TarjetaSlugDisponibleResponse(SchemaBase):
    """
    GET /tarjetas/public/slug-disponible/{slug}: si ese slug se puede usar en
    me.svelpy.com/{slug}. El slug actual de la tarjeta propia cuenta como disponible.
    """

    slug: str
    disponible: bool

    model_config = ConfigDict(json_schema_extra={"example": {"slug": "dra-ana-perez", "disponible": True}})


class TarjetasDespublicadasResponse(SchemaBase):
    """Resultado de POST /tarjetas/despublicar-vencidas: cuántas tarjetas se despublicaron."""

    despublicadas: int

    model_config = ConfigDict(json_schema_extra={"example": {"despublicadas": 3}})


# =================================
# Ronda 2: schemas con relaciones
# =================================

class TarjetaCreateNested(TarjetaCreate):
    """
    POST /tarjetas: la tarjeta con su árbol, en una sola transacción. theme,
    seo y vitrina son opcionales: sin ellos el service los crea con sus valores
    por defecto (theme con el preset claro). Las 8 secciones las crea siempre el
    service.
    """

    theme: TarjetaThemeCreate | None = None
    seo: TarjetaSeoCreate | None = None
    vitrina: VitrinaCreateNested | None = None
    contactos: list[TarjetaContactoCreate] = Field(default_factory=list, max_length=TARJETA_CONTACTO_MAX)
    ubicaciones: list[TarjetaUbicacionCreateNested] = Field(default_factory=list, max_length=TARJETA_UBICACION_MAX)
    redes: list[TarjetaSocialCreate] = Field(default_factory=list, max_length=TARJETA_SOCIAL_MAX)
    educaciones: list[TarjetaEducacionCreate] = Field(default_factory=list, max_length=TARJETA_EDUCACION_MAX)
    certificaciones: list[TarjetaCertificacionCreate] = Field(
        default_factory=list, max_length=TARJETA_CERTIFICACION_MAX
    )
    faqs: list[TarjetaFaqCreate] = Field(default_factory=list, max_length=TARJETA_FAQ_MAX)

    @field_validator("contactos", mode="after")
    @classmethod
    def validate_contactos(cls, value: list[TarjetaContactoCreate]) -> list[TarjetaContactoCreate]:
        ensure_one_primary_per_tipo(value)
        return value

    @field_validator("redes", mode="after")
    @classmethod
    def validate_redes(cls, value: list[TarjetaSocialCreate]) -> list[TarjetaSocialCreate]:
        ensure_unique_red(value)
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **TARJETA_CREATE_EXAMPLE,
                "theme": TARJETA_THEME_CREATE_EXAMPLE,
                "seo": TARJETA_SEO_PUBLIC_EXAMPLE,
                "vitrina": VITRINA_CREATE_NESTED_EXAMPLE,
                "contactos": TARJETA_CONTACTO_CREATE_EXAMPLES,
                "ubicaciones": TARJETA_UBICACION_CREATE_NESTED_EXAMPLES,
                "redes": TARJETA_SOCIAL_CREATE_EXAMPLES,
                "educaciones": TARJETA_EDUCACION_CREATE_EXAMPLES,
                "certificaciones": TARJETA_CERTIFICACION_CREATE_EXAMPLES,
                "faqs": TARJETA_FAQ_CREATE_EXAMPLES,
            }
        }
    )


class TarjetaUpdateNested(TarjetaUpdate):
    """
    PATCH /tarjetas/{id}. Cada lista es el estado final deseado: ausente o null
    no se toca, [] elimina todos sus elementos (AGENTS.md §20). secciones lleva
    siempre las 8, con su id: solo se actualizan. theme, seo y vitrina se editan
    con sus propias rutas.
    """

    secciones: list[TarjetaSeccionNestedItem] | None = Field(
        default=None, min_length=TARJETA_SECCION_COUNT, max_length=TARJETA_SECCION_COUNT
    )
    contactos: list[TarjetaContactoNestedItem] | None = Field(default=None, max_length=TARJETA_CONTACTO_MAX)
    ubicaciones: list[TarjetaUbicacionNestedItem] | None = Field(default=None, max_length=TARJETA_UBICACION_MAX)
    redes: list[TarjetaSocialNestedItem] | None = Field(default=None, max_length=TARJETA_SOCIAL_MAX)
    educaciones: list[TarjetaEducacionNestedItem] | None = Field(default=None, max_length=TARJETA_EDUCACION_MAX)
    certificaciones: list[TarjetaCertificacionNestedItem] | None = Field(
        default=None, max_length=TARJETA_CERTIFICACION_MAX
    )
    faqs: list[TarjetaFaqNestedItem] | None = Field(default=None, max_length=TARJETA_FAQ_MAX)

    @field_validator("secciones", "ubicaciones", "educaciones", "certificaciones", "faqs", mode="after")
    @classmethod
    def validate_ids(cls, value: list | None) -> list | None:
        return None if value is None else validator_unique_ids(value)

    @field_validator("contactos", mode="after")
    @classmethod
    def validate_contactos(cls, value: list[TarjetaContactoNestedItem] | None) -> list[TarjetaContactoNestedItem] | None:
        if value is None:
            return None
        ensure_one_primary_per_tipo(value)
        return validator_unique_ids(value)

    @field_validator("redes", mode="after")
    @classmethod
    def validate_redes(cls, value: list[TarjetaSocialNestedItem] | None) -> list[TarjetaSocialNestedItem] | None:
        if value is None:
            return None
        ensure_unique_red(value)
        return validator_unique_ids(value)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **TARJETA_CREATE_EXAMPLE,
                "secciones": TARJETA_SECCION_NESTED_EXAMPLES,
                "contactos": TARJETA_CONTACTO_NESTED_EXAMPLES,
                "ubicaciones": TARJETA_UBICACION_NESTED_EXAMPLES,
                "redes": TARJETA_SOCIAL_NESTED_EXAMPLES,
                "educaciones": TARJETA_EDUCACION_NESTED_EXAMPLES,
                "certificaciones": TARJETA_CERTIFICACION_NESTED_EXAMPLES,
                "faqs": TARJETA_FAQ_NESTED_EXAMPLES,
            }
        }
    )


class TarjetaResponseItemList(TarjetaResponse):
    user: UsuarioRef

    # Ejemplo de GET /tarjetas: una tarjeta por cada usuario de ejemplo.
    PAGE_EXAMPLES: ClassVar[list[dict]] = [
        {**TARJETA_RESPONSE_EXAMPLE, "user": USUARIO_REF_EXAMPLES[0]},
        {
            **TARJETA_RESPONSE_EXAMPLE,
            "id": "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7c",
            "user_id": USUARIO_REF_EXAMPLES[1]["id"],
            "slug": "estudio-mamani-abogados",
            "rubro": "Derecho laboral",
            "prefijo": "Abg.",
            "nombres": "Luis Fernando",
            "apellidos": "Mamani Condori",
            "cargo": "Socio fundador",
            "nombre_empresa": "Estudio Mamani & Asociados",
            "acerca_de_mi": "Asesoría laboral para empresas y trabajadores desde 2010.",
            "profile_url": "https://res.cloudinary.com/demo/image/upload/v1/perfil-luis.jpg",
            "photo_usuario_url": "https://res.cloudinary.com/demo/image/upload/v1/foto-luis.jpg",
            "logo_empresa_url": "https://res.cloudinary.com/demo/image/upload/v1/logo-estudio.png",
            "nombre_empresa_posicion": "abajo",
            "cover_url": "https://res.cloudinary.com/demo/image/upload/v1/portada-estudio.jpg",
            "qr_pago_url": "https://res.cloudinary.com/demo/image/upload/v1/qr-estudio.png",
            "is_public": True,
            "published_at": "2026-01-12T09:00:00Z",
            "created_at": "2026-01-10T12:30:00Z",
            "updated_at": "2026-01-12T09:00:00Z",
            "user": USUARIO_REF_EXAMPLES[1],
        },
        {
            **TARJETA_RESPONSE_EXAMPLE,
            "id": "3f1c2a9e-8b7d-4c6e-9a1b-2c3d4e5f6a7d",
            "user_id": USUARIO_REF_EXAMPLES[2]["id"],
            "slug": "carla-rojas-disenio",
            "rubro": "Diseño gráfico",
            "prefijo": "Lic.",
            "nombres": "Carla",
            "apellidos": "Rojas Vargas",
            "cargo": "Diseñadora de marca",
            "nombre_empresa": "Estudio Kantuta",
            "acerca_de_mi": "Identidad visual para emprendimientos bolivianos.",
            "profile_url": "https://res.cloudinary.com/demo/image/upload/v1/perfil-carla.jpg",
            "photo_usuario_url": "https://res.cloudinary.com/demo/image/upload/v1/foto-carla.jpg",
            "logo_empresa_url": "https://res.cloudinary.com/demo/image/upload/v1/logo-kantuta.png",
            "nombre_empresa_posicion": "izquierda",
            "cover_url": "https://res.cloudinary.com/demo/image/upload/v1/portada-kantuta.jpg",
            "qr_pago_url": "https://res.cloudinary.com/demo/image/upload/v1/qr-kantuta.png",
            # Despublicada al vencer su plan: conserva la fecha de su última publicación.
            "is_public": False,
            "published_at": "2026-02-01T10:00:00Z",
            "created_at": "2026-01-31T09:40:00Z",
            "updated_at": "2026-02-08T00:00:00Z",
            "user": USUARIO_REF_EXAMPLES[2],
        },
    ]

    model_config = ConfigDict(json_schema_extra={"example": {**TARJETA_RESPONSE_EXAMPLE, "user": USUARIO_REF_EXAMPLE}})


class TarjetaResponseDetail(TarjetaResponse):
    """Embebe el mismo árbol que acepta TarjetaUpdateNested, más su usuario."""

    user: UsuarioResponse
    secciones: list[TarjetaSeccionResponse]
    contactos: list[TarjetaContactoResponse]
    ubicaciones: list[TarjetaUbicacionResponseDetail]
    redes: list[TarjetaSocialResponse]
    educaciones: list[TarjetaEducacionResponse]
    certificaciones: list[TarjetaCertificacionResponse]
    faqs: list[TarjetaFaqResponse]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                **TARJETA_RESPONSE_EXAMPLE,
                "user": USUARIO_RESPONSE_EXAMPLE,
                "secciones": TARJETA_SECCION_RESPONSE_EXAMPLES,
                "contactos": TARJETA_CONTACTO_RESPONSE_EXAMPLES,
                "ubicaciones": TARJETA_UBICACION_RESPONSE_DETAIL_EXAMPLES,
                "redes": TARJETA_SOCIAL_RESPONSE_EXAMPLES,
                "educaciones": TARJETA_EDUCACION_RESPONSE_EXAMPLES,
                "certificaciones": TARJETA_CERTIFICACION_RESPONSE_EXAMPLES,
                "faqs": TARJETA_FAQ_RESPONSE_EXAMPLES,
            }
        }
    )


# =================================
# Vista del dueño (GET /usuarios/me)
# =================================

TARJETA_RESPONSE_ME_EXAMPLE = {
    **TARJETA_RESPONSE_EXAMPLE,
    "theme": TARJETA_THEME_RESPONSE_EXAMPLE,
    "seo": TARJETA_SEO_RESPONSE_EXAMPLE,
    "secciones": TARJETA_SECCION_RESPONSE_EXAMPLES,
    "contactos": TARJETA_CONTACTO_RESPONSE_EXAMPLES,
    "ubicaciones": TARJETA_UBICACION_RESPONSE_DETAIL_EXAMPLES,
    "redes": TARJETA_SOCIAL_RESPONSE_EXAMPLES,
    "educaciones": TARJETA_EDUCACION_RESPONSE_EXAMPLES,
    "certificaciones": TARJETA_CERTIFICACION_RESPONSE_EXAMPLES,
    "faqs": TARJETA_FAQ_RESPONSE_EXAMPLES,
    "vitrina": VITRINA_RESPONSE_DETAIL_EXAMPLE,
}


class TarjetaResponseMe(TarjetaResponse):
    """
    La tarjeta completa, tal como la ve su dueño: el mismo árbol que la lectura
    pública por slug, pero con todas las filas (visibles y ocultas), sin quitar
    precios y con is_visible, orden y fechas, para que decida qué editar.

    Excepción a §17: theme, seo y vitrina son Extensiones 1:1 con rutas propias,
    pero aquí se embeben para entregar la tarjeta en una sola llamada. Se editan
    igual que siempre, cada una en su ruta.
    """

    theme: TarjetaThemeResponse
    seo: TarjetaSeoResponse
    secciones: list[TarjetaSeccionResponse]
    contactos: list[TarjetaContactoResponse]
    ubicaciones: list[TarjetaUbicacionResponseDetail]
    redes: list[TarjetaSocialResponse]
    educaciones: list[TarjetaEducacionResponse]
    certificaciones: list[TarjetaCertificacionResponse]
    faqs: list[TarjetaFaqResponse]
    vitrina: VitrinaResponseDetail

    model_config = ConfigDict(json_schema_extra={"example": TARJETA_RESPONSE_ME_EXAMPLE})


# Vive aquí y no en usuario/schemas.py porque este módulo ya importa usuario/schemas:
# definirlo allá crearía un import circular entre los dos dominios.
class UsuarioResponseMe(UsuarioResponseDetail):
    """
    GET /usuarios/me: el usuario, su plan y su tarjeta completa (null si todavía
    no la creó). Excepción a §20: la tarjeta apunta al usuario ("me apuntan")
    y aun así se embebe, porque es una por usuario y el /me la entrega entera.
    """

    tarjeta: TarjetaResponseMe | None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {**USUARIO_RESPONSE_EXAMPLE, "plan": PLAN_RESPONSE_EXAMPLE, "tarjeta": TARJETA_RESPONSE_ME_EXAMPLE}
        }
    )
