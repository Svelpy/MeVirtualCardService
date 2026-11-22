from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.config import Settings
from app.domains.auth.schemas import CurrentUser
from app.domains.imagenes.services import ImagenService
from app.domains.tarjeta.repositories import TarjetaRepository
from app.domains.tarjeta.services import tarjeta_image_folder, tarjeta_scope_for
from app.domains.vitrina.repositories import VitrinaRepository
from app.domains.vitrina_categoria.repositories import VitrinaCategoriaRepository
from app.domains.vitrina_item.models import VitrinaItem
from app.domains.vitrina_item.repositories import VitrinaItemRepository
from app.domains.vitrina_item.schemas import (
    VitrinaItemCreateNested,
    VitrinaItemPublic,
    VitrinaItemResponseItemList,
    VitrinaItemUpdateNested,
)
from app.domains.vitrina_item_imagen.models import VitrinaItemImagen
from app.domains.vitrina_item_imagen.repositories import VitrinaItemImagenRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse
from app.shared.services.nested_sync import apply_sync


def _invalid(field: str, message: str) -> AppException:
    return AppException(
        "Los datos enviados no son válidos.",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        ErrorCode.VALIDATION_ERROR,
        details={field: message},
    )


def _ensure_precio_anterior(precio: Decimal | None, precio_anterior: Decimal | None) -> None:
    if precio_anterior is not None and (precio is None or precio_anterior <= precio):
        raise _invalid("precio_anterior", "El precio anterior requiere un precio y debe ser mayor que él.")


def _image_folder(vitrina_id: UUID) -> str:
    return f"{tarjeta_image_folder(vitrina_id)}/vitrina"  # vitrina.id = tarjeta.id


class VitrinaItemService:
    @staticmethod
    async def list(
        db_session: AsyncSession,
        actor: CurrentUser,
        *,
        page: int,
        per_page: int,
        vitrina_id: UUID | None = None,
        categoria_id: UUID | None = None,
        is_visible: bool | None = None,
    ) -> PaginatedResponse[VitrinaItemResponseItemList]:
        items, total = await VitrinaItemRepository.list(
            db_session,
            scope=tarjeta_scope_for(actor),
            page=page,
            per_page=per_page,
            vitrina_id=vitrina_id,
            categoria_id=categoria_id,
            is_visible=is_visible,
        )
        return PaginatedResponse[VitrinaItemResponseItemList].build(items, total=total, page=page, per_page=per_page)

    @staticmethod
    async def list_public(
        db_session: AsyncSession,
        *,
        vitrina_id: UUID,
        page: int,
        per_page: int,
        categoria_id: UUID | None = None,
    ) -> PaginatedResponse[VitrinaItemPublic]:
        """Solo de una tarjeta que se ve en público; si no, 404 como si no existiera."""
        if not await TarjetaRepository.is_public(db_session, vitrina_id, utc_now()):
            raise AppException("Vitrina no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        items, total = await VitrinaItemRepository.list_public(
            db_session, vitrina_id=vitrina_id, page=page, per_page=per_page, categoria_id=categoria_id
        )
        return PaginatedResponse[VitrinaItemPublic].build(items, total=total, page=page, per_page=per_page)

    @staticmethod
    async def get(
        db_session: AsyncSession,
        item_id: UUID,
        actor: CurrentUser,
        *,
        include_deleted: bool = False,
    ) -> VitrinaItem:
        item = await VitrinaItemRepository.get(
            db_session, item_id, scope=tarjeta_scope_for(actor), include_deleted=include_deleted, detail=True
        )
        if item is None:
            raise AppException("Item no encontrado.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return item

    @staticmethod
    async def create(
        db_session: AsyncSession,
        data: VitrinaItemCreateNested,
        actor: CurrentUser,
        settings: Settings,
    ) -> VitrinaItem:
        # Referencia recibida (§22): existe, no está eliminada y está en el alcance del actor.
        if await VitrinaRepository.get(db_session, data.vitrina_id, scope=tarjeta_scope_for(actor)) is None:
            raise _invalid("vitrina_id", "La vitrina no existe.")
        if data.categoria_id is not None:
            await VitrinaItemService._ensure_categoria(db_session, data.categoria_id, data.vitrina_id)
        new_images = {f"imagenes -> {index} -> url": imagen.url for index, imagen in enumerate(data.imagenes)}
        await ImagenService.ensure_new_images(db_session, new_images, settings)

        now = utc_now()
        audit = {"created_at": now, "updated_at": now, "created_by": actor.id}
        item = VitrinaItem(**data.model_dump(exclude={"imagenes"}), **audit)
        db_session.add(item)
        for imagen in data.imagenes:
            db_session.add(VitrinaItemImagen(item_id=item.id, **imagen.model_dump(), **audit))
        await db_session.commit()
        await ImagenService.confirm(new_images.values(), _image_folder(item.vitrina_id), settings)
        return await VitrinaItemService.get(db_session, item.id, actor)

    @staticmethod
    async def update(
        db_session: AsyncSession,
        item_id: UUID,
        data: VitrinaItemUpdateNested,
        actor: CurrentUser,
        settings: Settings,
    ) -> VitrinaItem:
        item = await VitrinaItemService.get(db_session, item_id, actor)
        changes = {
            field: value
            for field, value in data.model_dump(exclude_unset=True, exclude={"imagenes"}).items()
            if getattr(item, field) != value
        }
        if changes.get("categoria_id") is not None:
            await VitrinaItemService._ensure_categoria(db_session, changes["categoria_id"], item.vitrina_id)
        # Si llega solo uno de los dos precios, se compara con el valor guardado.
        _ensure_precio_anterior(
            changes.get("precio", item.precio), changes.get("precio_anterior", item.precio_anterior)
        )
        new_images, replaced = _image_changes(item.imagenes, data.imagenes)
        await ImagenService.ensure_new_images(db_session, new_images, settings)

        now = utc_now()
        for field, value in changes.items():
            setattr(item, field, value)
        if data.imagenes is not None:
            await apply_sync(
                db_session,
                field="imagenes",
                existing=item.imagenes,
                items=data.imagenes,
                build=lambda imagen: VitrinaItemImagen(
                    item_id=item.id, **imagen.model_dump(exclude={"id"}), created_by=actor.id
                ),
                now=now,
                actor_id=actor.id,
            )

        if changes or data.imagenes is not None:
            item.updated_at = now
            item.updated_by = actor.id
            await db_session.commit()
            await ImagenService.confirm(new_images.values(), _image_folder(item.vitrina_id), settings)
            await ImagenService.delete_replaced(replaced)
        return await VitrinaItemService.get(db_session, item_id, actor)

    @staticmethod
    async def delete(db_session: AsyncSession, item_id: UUID, actor: CurrentUser) -> None:
        item = await VitrinaItemService.get(db_session, item_id, actor)
        now = utc_now()
        await VitrinaItemImagenRepository.mark_deleted_by_item(db_session, item_id, now, actor.id)
        VitrinaItemRepository.mark_deleted(item, now, actor.id)
        await db_session.commit()

    @staticmethod
    async def _ensure_categoria(db_session: AsyncSession, categoria_id: UUID, vitrina_id: UUID) -> None:
        if await VitrinaCategoriaRepository.get_in_vitrina(db_session, categoria_id, vitrina_id) is None:
            raise _invalid("categoria_id", "La categoría no existe en esta vitrina.")


def _image_changes(
    existing: Sequence[VitrinaItemImagen],
    items: Sequence[Any] | None,
) -> tuple[dict[str, str], list[str]]:
    """URLs nuevas (campo → URL) y URLs que el item deja de usar, antes de sincronizar."""
    if items is None:
        return {}, []
    by_id = {imagen.id: imagen for imagen in existing}
    received = {item.id for item in items if item.id is not None}
    new_images: dict[str, str] = {}
    replaced = [imagen.url for imagen in existing if imagen.id not in received]
    for index, item in enumerate(items):
        current = by_id.get(item.id) if item.id is not None else None
        if current is None or current.url != item.url:
            new_images[f"imagenes -> {index} -> url"] = item.url
            if current is not None:
                replaced.append(current.url)
    return new_images, replaced
