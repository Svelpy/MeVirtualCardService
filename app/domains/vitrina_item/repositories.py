from collections.abc import Collection, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import LoaderOption

from app.domains.tarjeta.repositories import TarjetaScope, tarjeta_ids_in_scope
from app.domains.vitrina_categoria.models import VitrinaCategoria
from app.domains.vitrina_item.models import VitrinaItem
from app.domains.vitrina_item_imagen.models import VitrinaItemImagen


def _imagenes() -> LoaderOption:
    return selectinload(VitrinaItem.imagenes.and_(VitrinaItemImagen.is_deleted.is_(False)))


class VitrinaItemRepository:
    """Hija paginada de la vitrina; aplica el alcance de su tarjeta (vitrina.id = tarjeta.id)."""

    @staticmethod
    async def get(
        db_session: AsyncSession,
        item_id: UUID,
        *,
        scope: TarjetaScope,
        include_deleted: bool = False,
        detail: bool = False,
    ) -> VitrinaItem | None:
        """detail carga el árbol de VitrinaItemResponseDetail: su categoría y sus imágenes."""
        tarjeta_ids = tarjeta_ids_in_scope(scope, include_deleted=include_deleted)
        query = select(VitrinaItem).where(VitrinaItem.id == item_id, VitrinaItem.vitrina_id.in_(tarjeta_ids))
        if not include_deleted:
            query = query.where(VitrinaItem.is_deleted.is_(False))
        if detail:
            query = query.options(selectinload(VitrinaItem.categoria), _imagenes())
        query = query.execution_options(populate_existing=True)
        return (await db_session.execute(query)).scalars().first()

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        scope: TarjetaScope,
        page: int,
        per_page: int,
        vitrina_id: UUID | None,
        categoria_id: UUID | None,
        is_visible: bool | None,
    ) -> tuple[Sequence[VitrinaItem], int]:
        conditions = [VitrinaItem.is_deleted.is_(False), VitrinaItem.vitrina_id.in_(tarjeta_ids_in_scope(scope))]
        if vitrina_id is not None:
            conditions.append(VitrinaItem.vitrina_id == vitrina_id)
        if categoria_id is not None:
            conditions.append(VitrinaItem.categoria_id == categoria_id)
        if is_visible is not None:
            conditions.append(VitrinaItem.is_visible.is_(is_visible))
        return await VitrinaItemRepository._page(
            db_session, conditions, page, per_page, selectinload(VitrinaItem.categoria)
        )

    @staticmethod
    async def list_public(
        db_session: AsyncSession,
        *,
        vitrina_id: UUID,
        page: int,
        per_page: int,
        categoria_id: UUID | None,
    ) -> tuple[Sequence[VitrinaItem], int]:
        """
        Items visibles, sin los de una categoría oculta. Que la vitrina sea
        pública lo comprueba antes el service.
        """
        visible_categorias = select(VitrinaCategoria.id).where(
            VitrinaCategoria.vitrina_id == vitrina_id,
            VitrinaCategoria.is_deleted.is_(False),
            VitrinaCategoria.is_visible.is_(True),
        )
        conditions = [
            VitrinaItem.vitrina_id == vitrina_id,
            VitrinaItem.is_deleted.is_(False),
            VitrinaItem.is_visible.is_(True),
            or_(VitrinaItem.categoria_id.is_(None), VitrinaItem.categoria_id.in_(visible_categorias)),
        ]
        if categoria_id is not None:
            conditions.append(VitrinaItem.categoria_id == categoria_id)
        return await VitrinaItemRepository._page(db_session, conditions, page, per_page, _imagenes())

    @staticmethod
    async def exists_for_categorias(db_session: AsyncSession, categoria_ids: Collection[UUID]) -> bool:
        """Integridad (§19): items no eliminados que usan alguna de esas categorías, sin alcance."""
        query = select(
            exists().where(VitrinaItem.categoria_id.in_(categoria_ids), VitrinaItem.is_deleted.is_(False))
        )
        return bool((await db_session.execute(query)).scalar())

    @staticmethod
    def mark_deleted(item: VitrinaItem, now: datetime, actor_id: UUID) -> None:
        item.is_deleted = True
        item.deleted_at = now
        item.deleted_by = actor_id
        item.updated_at = now
        item.updated_by = actor_id

    @staticmethod
    async def mark_deleted_by_vitrina(db_session: AsyncSession, vitrina_id: UUID, now: datetime, actor_id: UUID) -> None:
        """Cascada (§19): los items de la vitrina; sus imágenes las marca VitrinaItemImagenRepository."""
        await db_session.execute(
            update(VitrinaItem)
            .where(VitrinaItem.vitrina_id == vitrina_id, VitrinaItem.is_deleted.is_(False))
            .values(is_deleted=True, deleted_at=now, deleted_by=actor_id, updated_at=now, updated_by=actor_id)
        )

    @staticmethod
    async def _page(
        db_session: AsyncSession,
        conditions: Sequence[ColumnElement[bool]],
        page: int,
        per_page: int,
        loader: LoaderOption,
    ) -> tuple[Sequence[VitrinaItem], int]:
        total = (await db_session.execute(select(func.count()).select_from(VitrinaItem).where(*conditions))).scalar_one()
        query = (
            select(VitrinaItem)
            .where(*conditions)
            .options(loader)
            # Orden propio de la vitrina: el que elige el dueño.
            .order_by(VitrinaItem.orden, VitrinaItem.created_at.desc(), VitrinaItem.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return (await db_session.execute(query)).scalars().all(), total
