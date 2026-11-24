from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import BaseModel, utc_now
from app.core.config import Settings
from app.domains.auth.schemas import CurrentUser
from app.domains.imagenes.services import ImagenService
from app.domains.tarjeta.models import Tarjeta
from app.domains.tarjeta.repositories import TarjetaRepository, TarjetaScope
from app.domains.tarjeta.schemas import (
    TarjetaCreate,
    TarjetaCreateNested,
    TarjetaResponseItemList,
    TarjetaUpdateNested,
)
from app.domains.tarjeta_certificacion.models import TarjetaCertificacion
from app.domains.tarjeta_certificacion.repositories import TarjetaCertificacionRepository
from app.domains.tarjeta_contacto.models import TarjetaContacto
from app.domains.tarjeta_contacto.repositories import TarjetaContactoRepository
from app.domains.tarjeta_educacion.models import TarjetaEducacion
from app.domains.tarjeta_educacion.repositories import TarjetaEducacionRepository
from app.domains.tarjeta_faq.models import TarjetaFaq
from app.domains.tarjeta_faq.repositories import TarjetaFaqRepository
from app.domains.tarjeta_seccion.models import TarjetaSeccion
from app.domains.tarjeta_seccion.repositories import TarjetaSeccionRepository
from app.domains.tarjeta_seo.models import TarjetaSeo
from app.domains.tarjeta_seo.repositories import TarjetaSeoRepository
from app.domains.tarjeta_social.models import TarjetaSocial
from app.domains.tarjeta_social.repositories import TarjetaSocialRepository
from app.domains.tarjeta_theme.models import TarjetaTheme
from app.domains.tarjeta_theme.repositories import TarjetaThemeRepository
from app.domains.tarjeta_theme.schemas import THEME_PRESETS, TarjetaThemeCreate
from app.domains.tarjeta_ubicacion.models import TarjetaUbicacion
from app.domains.tarjeta_ubicacion.repositories import TarjetaUbicacionRepository
from app.domains.ubicacion_horario.models import UbicacionHorario
from app.domains.ubicacion_horario.repositories import UbicacionHorarioRepository
from app.domains.usuario.repositories import UsuarioRepository
from app.domains.vitrina.models import Vitrina
from app.domains.vitrina.repositories import VitrinaRepository
from app.domains.vitrina.schemas import VitrinaCreateNested
from app.domains.vitrina_categoria.models import VitrinaCategoria
from app.domains.vitrina_categoria.repositories import VitrinaCategoriaRepository
from app.domains.vitrina_item.models import VitrinaItem
from app.domains.vitrina_item.repositories import VitrinaItemRepository
from app.domains.vitrina_item_imagen.models import VitrinaItemImagen
from app.domains.vitrina_item_imagen.repositories import VitrinaItemImagenRepository
from app.shared.enums import ClaveSeccion
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse
from app.shared.services.nested_sync import apply_sync, mark_deleted
from app.shared.services.permissions import TARJETA_GLOBAL_SCOPE_ROLES, TARJETA_OWNER_SCOPE_ROLES


# Este service no importa los services de sus hijas: ellas importan de aquí
# tarjeta_scope_for, y el import sería circular. De sus hijas usa models,
# schemas y repositories.

# Campos con una URL de POST /imagenes/uploads.
IMAGE_FIELDS = ("profile_url", "photo_usuario_url", "logo_empresa_url", "cover_url", "qr_pago_url")
TARJETA_FIELDS = frozenset(TarjetaCreate.model_fields)

# Hijas embebidas sin nietos: campo del schema → model. Las secciones (fijas) y
# las ubicaciones (con sus horarios) tienen su propio tratamiento.
SIMPLE_CHILDREN: dict[str, type[BaseModel]] = {
    "contactos": TarjetaContacto,
    "redes": TarjetaSocial,
    "educaciones": TarjetaEducacion,
    "certificaciones": TarjetaCertificacion,
    "faqs": TarjetaFaq,
}


def tarjeta_scope_for(actor: CurrentUser) -> TarjetaScope:
    """
    Única resolución del alcance de la tarjeta y de todo su árbol (§24): la
    usan también sus hijas y extensiones, que aplican el alcance de su padre.
    """
    if actor.role in TARJETA_GLOBAL_SCOPE_ROLES:
        return TarjetaScope(all=True)
    if actor.role in TARJETA_OWNER_SCOPE_ROLES:
        return TarjetaScope(user_id=actor.id)
    return TarjetaScope()  # alcance vacío: no devuelve filas


@dataclass(frozen=True)
class NewImages:
    """URLs nuevas de una tarjeta recién agregada, por carpeta: se confirman después del commit."""

    tarjeta: list[str]
    vitrina: list[str]


def tarjeta_image_folder(tarjeta_id: UUID) -> str:
    """Carpeta de Cloudinary de las imágenes de una tarjeta y de su árbol."""
    return f"tarjetas/{tarjeta_id}"


def vitrina_image_folder(vitrina_id: UUID) -> str:
    """Carpeta de las imágenes de los items de la vitrina (vitrina.id = tarjeta.id)."""
    return f"{tarjeta_image_folder(vitrina_id)}/vitrina"


def _not_found() -> AppException:
    return AppException("Tarjeta no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)


def _conflict(message: str, details: dict[str, str] | None = None) -> AppException:
    return AppException(message, status.HTTP_409_CONFLICT, ErrorCode.CONFLICT, details=details)


class TarjetaService:
    @staticmethod
    async def list(
        db_session: AsyncSession,
        actor: CurrentUser,
        *,
        page: int,
        per_page: int,
        user_id: UUID | None = None,
        is_public: bool | None = None,
    ) -> PaginatedResponse[TarjetaResponseItemList]:
        tarjetas, total = await TarjetaRepository.list(
            db_session,
            scope=tarjeta_scope_for(actor),
            page=page,
            per_page=per_page,
            user_id=user_id,
            is_public=is_public,
        )
        return PaginatedResponse[TarjetaResponseItemList].build(tarjetas, total=total, page=page, per_page=per_page)

    @staticmethod
    async def get(
        db_session: AsyncSession,
        tarjeta_id: UUID,
        actor: CurrentUser,
        *,
        include_deleted: bool = False,
    ) -> Tarjeta:
        tarjeta = await TarjetaRepository.get(
            db_session, tarjeta_id, scope=tarjeta_scope_for(actor), include_deleted=include_deleted, detail=True
        )
        if tarjeta is None:
            raise _not_found()
        return tarjeta

    @staticmethod
    async def get_public(
        db_session: AsyncSession,
        *,
        tarjeta_id: UUID | None = None,
        slug: str | None = None,
    ) -> Tarjeta:
        """Publicada, con su dueño activo y el plan vigente; si no, 404 como si no existiera."""
        tarjeta = await TarjetaRepository.get_public(db_session, utc_now(), tarjeta_id=tarjeta_id, slug=slug)
        if tarjeta is None:
            raise _not_found()
        return tarjeta

    @staticmethod
    async def create(
        db_session: AsyncSession,
        data: TarjetaCreateNested,
        actor: CurrentUser,
        settings: Settings,
    ) -> Tarjeta:
        """La crea su dueño, una por usuario, con su árbol en una sola transacción."""
        tarjeta, images = await TarjetaService.add_new(
            db_session, data, user_id=actor.id, created_by=actor.id, settings=settings
        )
        await db_session.commit()
        await ImagenService.confirm(images.tarjeta, tarjeta_image_folder(tarjeta.id), settings)
        await ImagenService.confirm(images.vitrina, vitrina_image_folder(tarjeta.id), settings)
        return await TarjetaService.get(db_session, tarjeta.id, actor)

    @staticmethod
    async def add_new(
        db_session: AsyncSession,
        data: TarjetaCreateNested,
        *,
        user_id: UUID,
        created_by: UUID,
        settings: Settings,
    ) -> tuple[Tarjeta, NewImages]:
        """
        Agrega a la sesión la tarjeta de user_id con todo su árbol, sin commit. Lo
        comparten POST /tarjetas y el registro público, que crea usuario y tarjeta
        en la misma transacción. Sin theme, seo o vitrina se crean con sus valores
        por defecto (theme claro); las 8 secciones las crea siempre el service.
        Devuelve las imágenes nuevas, que se confirman después del commit.
        """
        if await TarjetaRepository.exists_for_user(db_session, user_id):
            raise _conflict("Ya tienes una tarjeta.")
        await TarjetaService._ensure_slug_available(db_session, data.slug)
        new_images = {field: url for field in IMAGE_FIELDS if (url := getattr(data, field)) is not None}
        if data.seo is not None and data.seo.og_image_url is not None:
            new_images["seo -> og_image_url"] = data.seo.og_image_url
        vitrina = data.vitrina or VitrinaCreateNested()
        vitrina_images = {
            f"vitrina -> items -> {index} -> imagenes -> {position} -> url": imagen.url
            for index, item in enumerate(vitrina.items)
            for position, imagen in enumerate(item.imagenes)
        }
        await ImagenService.ensure_new_images(db_session, {**new_images, **vitrina_images}, settings)

        now = utc_now()
        audit = {"created_at": now, "updated_at": now, "created_by": created_by}
        tarjeta = Tarjeta(**data.model_dump(include=TARJETA_FIELDS), user_id=user_id, **audit)
        db_session.add(tarjeta)
        await db_session.flush()  # el árbol apunta a tarjeta.id

        theme = data.theme or TarjetaThemeCreate()
        preset_values = THEME_PRESETS[theme.preset]
        db_session.add(TarjetaTheme(id=tarjeta.id, **theme.model_dump(), **preset_values, **audit))
        db_session.add(TarjetaSeo(id=tarjeta.id, **(data.seo.model_dump() if data.seo else {}), **audit))
        db_session.add(Vitrina(id=tarjeta.id, **vitrina.model_dump(exclude={"categorias", "items"}), **audit))
        for categoria in vitrina.categorias:
            db_session.add(VitrinaCategoria(vitrina_id=tarjeta.id, **categoria.model_dump(), **audit))
        for item in vitrina.items:
            vitrina_item = VitrinaItem(vitrina_id=tarjeta.id, **item.model_dump(exclude={"imagenes"}), **audit)
            db_session.add(vitrina_item)
            for imagen in item.imagenes:
                db_session.add(VitrinaItemImagen(item_id=vitrina_item.id, **imagen.model_dump(), **audit))
        for orden, clave in enumerate(ClaveSeccion):
            db_session.add(TarjetaSeccion(tarjeta_id=tarjeta.id, clave=clave, orden=orden, **audit))
        for field, model in SIMPLE_CHILDREN.items():
            for item in getattr(data, field):
                db_session.add(model(tarjeta_id=tarjeta.id, **item.model_dump(), **audit))
        for item in data.ubicaciones:
            ubicacion = TarjetaUbicacion(tarjeta_id=tarjeta.id, **item.model_dump(exclude={"horarios"}), **audit)
            db_session.add(ubicacion)
            for horario in item.horarios:
                db_session.add(UbicacionHorario(ubicacion_id=ubicacion.id, **horario.model_dump(), **audit))
        await db_session.flush()
        return tarjeta, NewImages(tarjeta=list(new_images.values()), vitrina=list(vitrina_images.values()))

    @staticmethod
    async def update(
        db_session: AsyncSession,
        tarjeta_id: UUID,
        data: TarjetaUpdateNested,
        actor: CurrentUser,
        settings: Settings,
    ) -> Tarjeta:
        """
        Campos propios con exclude_unset, y cada lista recibida como estado final:
        eliminar, flush, actualizar y crear, en una sola transacción (§22).
        """
        tarjeta = await TarjetaService.get(db_session, tarjeta_id, actor)
        changes = {
            field: value
            for field, value in data.model_dump(exclude_unset=True, include=TARJETA_FIELDS).items()
            if getattr(tarjeta, field) != value
        }
        if "slug" in changes:
            await TarjetaService._ensure_slug_available(db_session, changes["slug"])
        new_images = {field: changes[field] for field in IMAGE_FIELDS if changes.get(field) is not None}
        replaced = [getattr(tarjeta, field) for field in IMAGE_FIELDS if field in changes and getattr(tarjeta, field)]
        await ImagenService.ensure_new_images(db_session, new_images, settings)

        now = utc_now()
        for field, value in changes.items():
            setattr(tarjeta, field, value)

        lists = [field for field in ("secciones", *SIMPLE_CHILDREN, "ubicaciones") if getattr(data, field) is not None]
        for field in lists:
            if field == "ubicaciones":
                await TarjetaService._sync_ubicaciones(db_session, tarjeta, data.ubicaciones, now, actor.id)
                continue
            model = TarjetaSeccion if field == "secciones" else SIMPLE_CHILDREN[field]
            # Las secciones traen siempre su id (schema): nunca se crean ni se eliminan.
            await apply_sync(
                db_session,
                field=field,
                existing=getattr(tarjeta, field),
                items=getattr(data, field),
                build=lambda item, model=model: model(
                    tarjeta_id=tarjeta.id, **item.model_dump(exclude={"id"}), created_by=actor.id
                ),
                now=now,
                actor_id=actor.id,
            )

        if changes or lists:
            tarjeta.updated_at = now
            tarjeta.updated_by = actor.id
            await db_session.commit()
            await ImagenService.confirm(new_images.values(), tarjeta_image_folder(tarjeta.id), settings)
            await ImagenService.delete_replaced(replaced)
        return await TarjetaService.get(db_session, tarjeta_id, actor)

    @staticmethod
    async def delete(db_session: AsyncSession, tarjeta_id: UUID, actor: CurrentUser) -> None:
        """Cascada lógica (§19) sobre todo el árbol, con los mismos deleted_at y deleted_by."""
        tarjeta = await TarjetaService.get(db_session, tarjeta_id, actor)
        now = utc_now()
        # Los nietos (horarios, items y sus imágenes) se ubican por subconsulta desde la tarjeta.
        await UbicacionHorarioRepository.mark_deleted_by_tarjeta(db_session, tarjeta_id, now, actor.id)
        await VitrinaItemImagenRepository.mark_deleted_by_vitrina(db_session, tarjeta_id, now, actor.id)
        await VitrinaItemRepository.mark_deleted_by_vitrina(db_session, tarjeta_id, now, actor.id)
        await VitrinaCategoriaRepository.mark_deleted_by_vitrina(db_session, tarjeta_id, now, actor.id)
        for repository in (
            TarjetaThemeRepository,
            TarjetaSeoRepository,
            VitrinaRepository,
            TarjetaSeccionRepository,
            TarjetaContactoRepository,
            TarjetaUbicacionRepository,
            TarjetaSocialRepository,
            TarjetaEducacionRepository,
            TarjetaCertificacionRepository,
            TarjetaFaqRepository,
        ):
            await repository.mark_deleted_by_tarjeta(db_session, tarjeta_id, now, actor.id)
        TarjetaRepository.mark_deleted(tarjeta, now, actor.id)
        await db_session.commit()

    @staticmethod
    async def publicar(db_session: AsyncSession, tarjeta_id: UUID, actor: CurrentUser) -> Tarjeta:
        """Exige que el dueño esté activo, con el email verificado y el plan vigente."""
        tarjeta = await TarjetaService.get(db_session, tarjeta_id, actor)
        dueno = await UsuarioRepository.get(db_session, tarjeta.user_id)
        now = utc_now()
        if dueno is None or not dueno.is_active:
            raise _conflict("La cuenta del dueño está dada de baja.")
        if dueno.email_verified_at is None:
            raise _conflict("Verifica tu email antes de publicar la tarjeta.")
        if dueno.plan_vence_at <= now:
            raise _conflict("El plan venció: renuévalo para publicar la tarjeta.")
        if not tarjeta.is_public:
            tarjeta.is_public = True
            tarjeta.published_at = now
            tarjeta.updated_at = now
            tarjeta.updated_by = actor.id
            await db_session.commit()
        return await TarjetaService.get(db_session, tarjeta_id, actor)

    @staticmethod
    async def despublicar(db_session: AsyncSession, tarjeta_id: UUID, actor: CurrentUser) -> Tarjeta:
        tarjeta = await TarjetaService.get(db_session, tarjeta_id, actor)
        if tarjeta.is_public:
            tarjeta.is_public = False
            tarjeta.updated_at = utc_now()
            tarjeta.updated_by = actor.id
            await db_session.commit()
        return await TarjetaService.get(db_session, tarjeta_id, actor)

    @staticmethod
    async def despublicar_vencidas(db_session: AsyncSession, actor: CurrentUser | None = None) -> int:
        """
        Tarea del sistema: despublica las tarjetas con el plan vencido. La ejecuta
        el cron (jobs/despublicar_vencidas.py, sin actor) o un admin desde
        POST /tarjetas/despublicar-vencidas. Al renovar, el dueño la vuelve a publicar.
        """
        count = await TarjetaRepository.unpublish_expired(db_session, utc_now(), actor.id if actor else None)
        await db_session.commit()
        return count

    @staticmethod
    async def _sync_ubicaciones(
        db_session: AsyncSession,
        tarjeta: Tarjeta,
        items: Sequence[Any],
        now: datetime,
        actor_id: UUID,
    ) -> None:
        """Ubicaciones y, dentro de cada una, sus horarios (horarios ausente o null no se tocan)."""
        applied = await apply_sync(
            db_session,
            field="ubicaciones",
            existing=tarjeta.ubicaciones,
            items=items,
            build=lambda item: TarjetaUbicacion(
                tarjeta_id=tarjeta.id, **item.model_dump(exclude={"id", "horarios"}), created_by=actor_id
            ),
            now=now,
            actor_id=actor_id,
            exclude=frozenset({"horarios"}),
        )
        # Cascada (§19): los horarios de las ubicaciones eliminadas.
        for ubicacion in applied.deleted:
            for horario in ubicacion.horarios:
                mark_deleted(horario, now, actor_id)
        for item, ubicacion in applied.created:
            for horario in item.horarios or []:
                db_session.add(
                    UbicacionHorario(
                        ubicacion_id=ubicacion.id, **horario.model_dump(exclude={"id"}), created_by=actor_id
                    )
                )
        updated = {item.id: ubicacion for item, ubicacion in applied.updated}
        for index, item in enumerate(items):
            ubicacion = updated.get(item.id) if item.id is not None else None
            if ubicacion is None or item.horarios is None:
                continue
            await apply_sync(
                db_session,
                field=f"ubicaciones -> {index} -> horarios",
                existing=ubicacion.horarios,
                items=item.horarios,
                build=lambda horario, ubicacion=ubicacion: UbicacionHorario(
                    ubicacion_id=ubicacion.id, **horario.model_dump(exclude={"id"}), created_by=actor_id
                ),
                now=now,
                actor_id=actor_id,
            )

    @staticmethod
    async def slug_disponible(db_session: AsyncSession, slug: str, actor: CurrentUser | None) -> bool:
        """
        Libre si ninguna tarjeta no eliminada lo usa. Con sesión, el slug actual de
        la tarjeta propia también cuenta como disponible: guardarlo no da 409.
        """
        tarjeta = await TarjetaRepository.get_by_slug(db_session, slug)
        return tarjeta is None or (actor is not None and tarjeta.user_id == actor.id)

    @staticmethod
    async def _ensure_slug_available(db_session: AsyncSession, slug: str) -> None:
        if await TarjetaRepository.get_by_slug(db_session, slug) is not None:
            raise _conflict("Ese slug ya está en uso.", details={"slug": "Ya está en uso."})
