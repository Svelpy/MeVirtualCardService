from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, text
from sqlmodel import Field, Relationship

from app.core.base_model import BaseModel, enum_type
from app.shared.enums import PosicionNombreEmpresa

if TYPE_CHECKING:
    from app.domains.tarjeta_certificacion.models import TarjetaCertificacion
    from app.domains.tarjeta_contacto.models import TarjetaContacto
    from app.domains.tarjeta_educacion.models import TarjetaEducacion
    from app.domains.tarjeta_faq.models import TarjetaFaq
    from app.domains.tarjeta_seccion.models import TarjetaSeccion
    from app.domains.tarjeta_seo.models import TarjetaSeo
    from app.domains.tarjeta_social.models import TarjetaSocial
    from app.domains.tarjeta_theme.models import TarjetaTheme
    from app.domains.tarjeta_ubicacion.models import TarjetaUbicacion
    from app.domains.usuario.models import Usuario
    from app.domains.vitrina.models import Vitrina


class Tarjeta(BaseModel, table=True):
    __tablename__ = "tarjeta"
    __table_args__ = (
        # Una tarjeta por usuario.
        Index(
            "uq_tarjeta_user_id_not_deleted",
            "user_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        # Al cambiar el slug o eliminar la tarjeta, el slug anterior queda libre.
        Index(
            "uq_tarjeta_slug_not_deleted",
            "slug",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$' AND length(slug) BETWEEN 3 AND 80",
            name="slug_formato",
        ),
        CheckConstraint("NOT is_public OR published_at IS NOT NULL", name="publicada_con_fecha"),
    )

    user_id: UUID = Field(foreign_key="usuario.id", nullable=False)
    slug: str = Field(sa_type=String(80), nullable=False)
    rubro: str = Field(sa_type=String(150), nullable=False)
    prefijo: str | None = Field(default=None, sa_type=String(30), nullable=True)
    nombres: str = Field(sa_type=String(150), nullable=False)
    apellidos: str | None = Field(default=None, sa_type=String(150), nullable=True)
    cargo: str | None = Field(default=None, sa_type=String(150), nullable=True)
    nombre_empresa: str | None = Field(default=None, sa_type=String(200), nullable=True)
    acerca_de_mi: str | None = Field(default=None, sa_type=Text, nullable=True)
    profile_url: str | None = Field(default=None, sa_type=Text, nullable=True)
    photo_usuario_url: str | None = Field(default=None, sa_type=Text, nullable=True)
    logo_empresa_url: str | None = Field(default=None, sa_type=Text, nullable=True)
    nombre_empresa_posicion: PosicionNombreEmpresa = Field(
        default=PosicionNombreEmpresa.DERECHA,
        sa_type=enum_type(PosicionNombreEmpresa, "posicion_nombre_empresa"),
        nullable=False,
    )
    cover_url: str | None = Field(default=None, sa_type=Text, nullable=True)
    qr_pago_url: str | None = Field(default=None, sa_type=Text, nullable=True)
    # Estado: solo cambia con los endpoints de acción publicar / despublicar.
    is_public: bool = Field(default=False, nullable=False)
    published_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True), nullable=True)

    # Referencia.
    user: "Usuario" = Relationship(sa_relationship_kwargs={"lazy": "raise"})

    # Extensiones 1:1 (no embebidas: se leen y editan con sus propias rutas).
    theme: "TarjetaTheme" = Relationship(sa_relationship_kwargs={"lazy": "raise", "uselist": False})
    seo: "TarjetaSeo" = Relationship(sa_relationship_kwargs={"lazy": "raise", "uselist": False})
    vitrina: "Vitrina" = Relationship(sa_relationship_kwargs={"lazy": "raise", "uselist": False})

    # Hijas embebidas.
    secciones: list["TarjetaSeccion"] = Relationship(
        sa_relationship_kwargs={"lazy": "raise", "order_by": "[TarjetaSeccion.orden, TarjetaSeccion.created_at]"}
    )
    contactos: list["TarjetaContacto"] = Relationship(
        sa_relationship_kwargs={"lazy": "raise", "order_by": "[TarjetaContacto.orden, TarjetaContacto.created_at]"}
    )
    ubicaciones: list["TarjetaUbicacion"] = Relationship(
        sa_relationship_kwargs={"lazy": "raise", "order_by": "[TarjetaUbicacion.orden, TarjetaUbicacion.created_at]"}
    )
    redes: list["TarjetaSocial"] = Relationship(
        sa_relationship_kwargs={"lazy": "raise", "order_by": "[TarjetaSocial.orden, TarjetaSocial.created_at]"}
    )
    educaciones: list["TarjetaEducacion"] = Relationship(
        sa_relationship_kwargs={"lazy": "raise", "order_by": "[TarjetaEducacion.orden, TarjetaEducacion.created_at]"}
    )
    certificaciones: list["TarjetaCertificacion"] = Relationship(
        sa_relationship_kwargs={
            "lazy": "raise",
            "order_by": "[TarjetaCertificacion.orden, TarjetaCertificacion.created_at]",
        }
    )
    faqs: list["TarjetaFaq"] = Relationship(
        sa_relationship_kwargs={"lazy": "raise", "order_by": "[TarjetaFaq.orden, TarjetaFaq.created_at]"}
    )
