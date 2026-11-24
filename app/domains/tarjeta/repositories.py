from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Select, exists, false, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import LoaderOption

# Los Relationship() se resuelven por nombre: las extensiones de Tarjeta y el
# plan de Usuario tienen que estar registrados antes de configurar los mappers.
import app.domains.plan.models  # noqa: F401
import app.domains.tarjeta_seo.models  # noqa: F401
import app.domains.tarjeta_theme.models  # noqa: F401
from app.domains.tarjeta.models import Tarjeta
from app.domains.tarjeta_certificacion.models import TarjetaCertificacion
from app.domains.tarjeta_contacto.models import TarjetaContacto
from app.domains.tarjeta_educacion.models import TarjetaEducacion
from app.domains.tarjeta_faq.models import TarjetaFaq
from app.domains.tarjeta_seccion.models import TarjetaSeccion
from app.domains.tarjeta_social.models import TarjetaSocial
from app.domains.tarjeta_ubicacion.models import TarjetaUbicacion
from app.domains.ubicacion_horario.models import UbicacionHorario
from app.domains.usuario.models import Usuario
from app.domains.vitrina.models import Vitrina
from app.domains.vitrina_categoria.models import VitrinaCategoria
from app.domains.vitrina_item.models import VitrinaItem
from app.domains.vitrina_item_imagen.models import VitrinaItemImagen


@dataclass(frozen=True)
class TarjetaScope:
    """Alcance (§24), sin roles: all = todas las tarjetas; user_id = solo la de ese dueño."""

    user_id: UUID | None = None
    all: bool = False


def _apply_scope(query: Select, scope: TarjetaScope) -> Select:
    if scope.all:
        return query
    if scope.user_id is not None:
        return query.where(Tarjeta.user_id == scope.user_id)
    return query.where(false())  # alcance vacío


def tarjeta_ids_in_scope(scope: TarjetaScope, *, include_deleted: bool = False) -> Select:
    """
    Subconsulta con los ids de las tarjetas dentro del alcance. Las hijas la usan
    para aplicar el alcance de su padre: Model.tarjeta_id.in_(...). Con
    include_deleted (auditoría) incluye las tarjetas eliminadas.
    """
    query = select(Tarjeta.id)
    if not include_deleted:
        query = query.where(Tarjeta.is_deleted.is_(False))
    return _apply_scope(query, scope)


def _public_condition(now: datetime) -> list[ColumnElement[bool]]:
    """Lectura anónima (§24): publicada, con su dueño activo y el plan vigente."""
    return [
        Tarjeta.is_deleted.is_(False),
        Tarjeta.is_public.is_(True),
        Usuario.id == Tarjeta.user_id,
        Usuario.is_deleted.is_(False),
        Usuario.is_active.is_(True),
        Usuario.plan_vence_at > now,
    ]


def _categoria_visible() -> ColumnElement[bool]:
    return VitrinaCategoria.is_deleted.is_(False) & VitrinaCategoria.is_visible.is_(True)


def _children(*, visible_only: bool) -> list[LoaderOption]:
    """Las hijas embebidas no eliminadas; para la lectura pública, solo las visibles."""

    def alive(model: type) -> ColumnElement[bool]:
        condition = model.is_deleted.is_(False)
        if visible_only and hasattr(model, "is_visible"):
            condition = condition & model.is_visible.is_(True)
        return condition

    return [
        selectinload(Tarjeta.secciones.and_(alive(TarjetaSeccion))),
        selectinload(Tarjeta.contactos.and_(alive(TarjetaContacto))),
        selectinload(Tarjeta.ubicaciones.and_(alive(TarjetaUbicacion))).selectinload(
            TarjetaUbicacion.horarios.and_(alive(UbicacionHorario))
        ),
        selectinload(Tarjeta.redes.and_(alive(TarjetaSocial))),
        selectinload(Tarjeta.educaciones.and_(alive(TarjetaEducacion))),
        selectinload(Tarjeta.certificaciones.and_(alive(TarjetaCertificacion))),
        selectinload(Tarjeta.faqs.and_(alive(TarjetaFaq))),
    ]


def _full_tree() -> list[LoaderOption]:
    """
    El árbol de TarjetaResponseMe: theme, seo, vitrina (categorías, items con su
    categoría e imágenes) y todas las hijas no eliminadas, visibles u ocultas.
    """
    return [
        selectinload(Tarjeta.theme),
        selectinload(Tarjeta.seo),
        selectinload(Tarjeta.vitrina).options(
            selectinload(Vitrina.categorias.and_(VitrinaCategoria.is_deleted.is_(False))),
            selectinload(Vitrina.items.and_(VitrinaItem.is_deleted.is_(False))).options(
                selectinload(VitrinaItem.categoria),
                selectinload(VitrinaItem.imagenes.and_(VitrinaItemImagen.is_deleted.is_(False))),
            ),
        ),
        *_children(visible_only=False),
    ]


class TarjetaRepository:
    @staticmethod
    async def get(
        db_session: AsyncSession,
        tarjeta_id: UUID,
        *,
        scope: TarjetaScope,
        include_deleted: bool = False,
        detail: bool = False,
    ) -> Tarjeta | None:
        """detail carga el árbol de TarjetaResponseDetail: su usuario y sus hijas embebidas."""
        query = select(Tarjeta).where(Tarjeta.id == tarjeta_id)
        if not include_deleted:
            query = query.where(Tarjeta.is_deleted.is_(False))
        if detail:
            query = query.options(selectinload(Tarjeta.user), *_children(visible_only=False))
        query = _apply_scope(query, scope).execution_options(populate_existing=True)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def get_full(db_session: AsyncSession, tarjeta_id: UUID, *, scope: TarjetaScope) -> Tarjeta | None:
        """La tarjeta no eliminada, dentro del alcance, con el árbol de TarjetaResponseMe."""
        query = select(Tarjeta).where(Tarjeta.id == tarjeta_id, Tarjeta.is_deleted.is_(False)).options(*_full_tree())
        query = _apply_scope(query, scope).execution_options(populate_existing=True)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def get_by_user(db_session: AsyncSession, user_id: UUID) -> Tarjeta | None:
        """La tarjeta no eliminada de ese dueño (una por usuario) con el árbol de TarjetaResponseMe."""
        query = (
            select(Tarjeta)
            .where(Tarjeta.user_id == user_id, Tarjeta.is_deleted.is_(False))
            .options(*_full_tree())
            .execution_options(populate_existing=True)
        )
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def get_public(
        db_session: AsyncSession,
        now: datetime,
        *,
        tarjeta_id: UUID | None = None,
        slug: str | None = None,
    ) -> Tarjeta | None:
        """La tarjeta publicada con todo su árbol visible, por id (el QR) o por slug."""
        query = (
            select(Tarjeta)
            .where(*_public_condition(now))
            .options(
                selectinload(Tarjeta.theme),
                selectinload(Tarjeta.seo),
                selectinload(Tarjeta.vitrina).options(
                    selectinload(Vitrina.categorias.and_(_categoria_visible())),
                    selectinload(
                        Vitrina.items.and_(
                            VitrinaItem.is_deleted.is_(False),
                            VitrinaItem.is_visible.is_(True),
                            # Sin los items de una categoría oculta. La foreign key compuesta
                            # garantiza que la categoría es de la misma vitrina.
                            or_(
                                VitrinaItem.categoria_id.is_(None),
                                VitrinaItem.categoria_id.in_(select(VitrinaCategoria.id).where(_categoria_visible())),
                            ),
                        )
                    ).selectinload(VitrinaItem.imagenes.and_(VitrinaItemImagen.is_deleted.is_(False))),
                ),
                *_children(visible_only=True),
            )
        )
        if tarjeta_id is not None:
            query = query.where(Tarjeta.id == tarjeta_id)
        if slug is not None:
            query = query.where(Tarjeta.slug == slug)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def get_by_slug(db_session: AsyncSession, slug: str) -> Tarjeta | None:
        """Unicidad: entre todas las tarjetas no eliminadas, sin alcance (§24)."""
        query = select(Tarjeta).where(Tarjeta.slug == slug, Tarjeta.is_deleted.is_(False))
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def exists_for_user(db_session: AsyncSession, user_id: UUID) -> bool:
        """Integridad: consulta todas las tarjetas no eliminadas, sin alcance (§24)."""
        query = select(exists().where(Tarjeta.user_id == user_id, Tarjeta.is_deleted.is_(False)))
        return bool((await db_session.execute(query)).scalar())

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        scope: TarjetaScope,
        page: int,
        per_page: int,
        user_id: UUID | None,
        is_public: bool | None,
    ) -> tuple[Sequence[Tarjeta], int]:
        conditions = [Tarjeta.is_deleted.is_(False)]
        if user_id is not None:
            conditions.append(Tarjeta.user_id == user_id)
        if is_public is not None:
            conditions.append(Tarjeta.is_public.is_(is_public))
        count_query = _apply_scope(select(func.count()).select_from(Tarjeta).where(*conditions), scope)
        total = (await db_session.execute(count_query)).scalar_one()
        query = (
            _apply_scope(select(Tarjeta).where(*conditions), scope)
            .options(selectinload(Tarjeta.user))
            .order_by(Tarjeta.created_at.desc(), Tarjeta.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return (await db_session.execute(query)).scalars().all(), total

    @staticmethod
    async def unpublish_for_user(db_session: AsyncSession, user_id: UUID, now: datetime, actor_id: UUID) -> None:
        await db_session.execute(
            update(Tarjeta)
            .where(Tarjeta.user_id == user_id, Tarjeta.is_public.is_(True), Tarjeta.is_deleted.is_(False))
            .values(is_public=False, updated_at=now, updated_by=actor_id)
        )

    @staticmethod
    async def unpublish_expired(db_session: AsyncSession, now: datetime, actor_id: UUID | None) -> int:
        """Despublica las tarjetas cuyo dueño tiene el plan vencido; devuelve cuántas."""
        expired_users = select(Usuario.id).where(Usuario.plan_vence_at <= now)
        result = await db_session.execute(
            update(Tarjeta)
            .where(
                Tarjeta.is_public.is_(True),
                Tarjeta.is_deleted.is_(False),
                Tarjeta.user_id.in_(expired_users),
            )
            # Desde el cron no hay actor: updated_by queda en NULL.
            .values(is_public=False, updated_at=now, updated_by=actor_id)
        )
        return result.rowcount

    @staticmethod
    def mark_deleted(tarjeta: Tarjeta, now: datetime, actor_id: UUID) -> None:
        tarjeta.is_deleted = True
        tarjeta.deleted_at = now
        tarjeta.deleted_by = actor_id
        tarjeta.updated_at = now
        tarjeta.updated_by = actor_id
