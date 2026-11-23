from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.config import Settings
from app.domains.auth.schemas import CurrentUser
from app.domains.imagenes.services import ImagenService
from app.domains.tarjeta.services import tarjeta_scope_for, vitrina_image_folder
from app.domains.vitrina.models import Vitrina
from app.domains.vitrina.repositories import VitrinaRepository
from app.domains.vitrina.schemas import VitrinaUpdateNested
from app.domains.vitrina_categoria.models import VitrinaCategoria
from app.domains.vitrina_item.models import VitrinaItem
from app.domains.vitrina_item.repositories import VitrinaItemRepository
from app.domains.vitrina_item_imagen.models import VitrinaItemImagen
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.services.nested_sync import apply_sync, mark_deleted


class VitrinaService:
    @staticmethod
    async def get(
        db_session: AsyncSession,
        vitrina_id: UUID,
        actor: CurrentUser,
        *,
        include_deleted: bool = False,
    ) -> Vitrina:
        vitrina = await VitrinaRepository.get(
            db_session, vitrina_id, scope=tarjeta_scope_for(actor), include_deleted=include_deleted, detail=True
        )
        if vitrina is None:
            raise AppException("Vitrina no encontrada.", status.HTTP_404_NOT_FOUND, ErrorCode.RESOURCE_NOT_FOUND)
        return vitrina

    @staticmethod
    async def update(
        db_session: AsyncSession,
        vitrina_id: UUID,
        data: VitrinaUpdateNested,
        actor: CurrentUser,
        settings: Settings,
    ) -> Vitrina:
        """
        Sus campos, sus items (con sus imágenes) y sus categorías, cada lista
        como estado final. Los items se sincronizan antes que las categorías:
        así una categoría se puede eliminar en la misma petición que deja de
        usarla. Una categoría que sigue con items no se elimina: 409.
        """
        vitrina = await VitrinaService.get(db_session, vitrina_id, actor)
        changes = {
            field: value
            for field, value in data.model_dump(exclude_unset=True, exclude={"categorias", "items"}).items()
            if getattr(vitrina, field) != value
        }
        new_images: dict[str, str] = {}
        replaced: list[str] = []
        if data.items is not None:
            _ensure_categorias(vitrina, data)
            new_images, replaced = _image_changes(vitrina.items, data.items)
            await ImagenService.ensure_new_images(db_session, new_images, settings)

        now = utc_now()
        for field, value in changes.items():
            setattr(vitrina, field, value)

        if data.items is not None:
            await _sync_items(db_session, vitrina, data.items, now, actor.id)
            await db_session.flush()  # el 409 de categorías ve los items ya actualizados

        if data.categorias is not None:

            async def ensure_unused(categorias: Sequence[VitrinaCategoria]) -> None:
                if await VitrinaItemRepository.exists_for_categorias(db_session, [c.id for c in categorias]):
                    raise AppException(
                        "Hay categorías con items: muévelos o elimínalos antes.",
                        status.HTTP_409_CONFLICT,
                        ErrorCode.CONFLICT,
                        details={"categorias": sorted(str(c.id) for c in categorias)},
                    )

            await apply_sync(
                db_session,
                field="categorias",
                existing=vitrina.categorias,
                items=data.categorias,
                build=lambda item: VitrinaCategoria(
                    vitrina_id=vitrina.id, **item.model_dump(exclude={"id"}), created_by=actor.id
                ),
                now=now,
                actor_id=actor.id,
                before_delete=ensure_unused,
            )

        if changes or data.categorias is not None or data.items is not None:
            vitrina.updated_at = now
            vitrina.updated_by = actor.id
            await db_session.commit()
            await ImagenService.confirm(new_images.values(), vitrina_image_folder(vitrina.id), settings)
            await ImagenService.delete_replaced(replaced)
        return await VitrinaService.get(db_session, vitrina_id, actor)


def _ensure_categorias(vitrina: Vitrina, data: VitrinaUpdateNested) -> None:
    """
    Referencia recibida (§22): la categoría de cada item es una categoría
    existente de esta vitrina que la petición conserva. Una categoría nueva
    todavía no tiene id: se crea primero y se asigna en una segunda petición.
    """
    available = {categoria.id for categoria in vitrina.categorias}
    if data.categorias is not None:
        available &= {categoria.id for categoria in data.categorias if categoria.id is not None}
    invalid = {
        f"items -> {index} -> categoria_id": "La categoría no existe en esta vitrina."
        for index, item in enumerate(data.items or [])
        if item.categoria_id is not None and item.categoria_id not in available
    }
    if invalid:
        raise AppException(
            "Los datos enviados no son válidos.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.VALIDATION_ERROR,
            details=invalid,
        )


async def _sync_items(
    db_session: AsyncSession,
    vitrina: Vitrina,
    items: Sequence[Any],
    now: datetime,
    actor_id: UUID,
) -> None:
    """Items y, dentro de cada uno, sus imágenes (imagenes ausente o null no se tocan)."""
    applied = await apply_sync(
        db_session,
        field="items",
        existing=vitrina.items,
        items=items,
        build=lambda item: VitrinaItem(
            vitrina_id=vitrina.id, **item.model_dump(exclude={"id", "imagenes"}), created_by=actor_id
        ),
        now=now,
        actor_id=actor_id,
        exclude=frozenset({"imagenes"}),
    )
    # Cascada (§19): las imágenes de los items eliminados.
    for item in applied.deleted:
        for imagen in item.imagenes:
            mark_deleted(imagen, now, actor_id)
    for received, item in applied.created:
        for imagen in received.imagenes or []:
            db_session.add(VitrinaItemImagen(item_id=item.id, **imagen.model_dump(exclude={"id"}), created_by=actor_id))
    updated = {received.id: item for received, item in applied.updated}
    for index, received in enumerate(items):
        item = updated.get(received.id) if received.id is not None else None
        if item is None or received.imagenes is None:
            continue
        await apply_sync(
            db_session,
            field=f"items -> {index} -> imagenes",
            existing=item.imagenes,
            items=received.imagenes,
            build=lambda imagen, item=item: VitrinaItemImagen(
                item_id=item.id, **imagen.model_dump(exclude={"id"}), created_by=actor_id
            ),
            now=now,
            actor_id=actor_id,
        )


def _image_changes(existing: Sequence[VitrinaItem], items: Sequence[Any]) -> tuple[dict[str, str], list[str]]:
    """
    URLs nuevas (campo → URL) y URLs que dejan de usarse, antes de sincronizar.
    Las imágenes de un item eliminado no se borran: quedan para su auditoría.
    """
    by_id = {item.id: item for item in existing}
    new_images: dict[str, str] = {}
    replaced: list[str] = []
    for index, received in enumerate(items):
        if received.imagenes is None:
            continue
        current = by_id.get(received.id) if received.id is not None else None
        current_images = {imagen.id: imagen for imagen in current.imagenes} if current is not None else {}
        kept = {imagen.id for imagen in received.imagenes if imagen.id is not None}
        replaced += [imagen.url for imagen_id, imagen in current_images.items() if imagen_id not in kept]
        for position, imagen in enumerate(received.imagenes):
            previous = current_images.get(imagen.id) if imagen.id is not None else None
            if previous is None or previous.url != imagen.url:
                new_images[f"items -> {index} -> imagenes -> {position} -> url"] = imagen.url
                if previous is not None:
                    replaced.append(previous.url)
    return new_images, replaced
