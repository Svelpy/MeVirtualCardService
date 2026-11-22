"""
Aplica el plan de sync.py sobre las hijas ya cargadas de un padre (AGENTS.md §22),
dentro de la transacción del service: eliminar, flush(), actualizar y crear.

Las hijas tienen índices únicos parciales con is_deleted = false (un contacto
principal por tipo, una cuenta por red, una imagen principal...). Si dos filas
existentes intercambian esos valores, un UPDATE intermedio violaría el índice.
Por eso las filas que cambian se marcan como eliminadas antes del primer flush:
salen del índice, y en el segundo flush vuelven con sus valores finales. Todo
ocurre dentro de la transacción, así que nadie ve ese estado intermedio.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import BaseModel
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.services.sync import ForeignChildError, plan_sync


@dataclass(frozen=True)
class AppliedSync[M: BaseModel]:
    deleted: tuple[M, ...]
    updated: tuple[tuple[Any, M], ...]  # (elemento recibido, model), cambie o no
    created: tuple[tuple[Any, M], ...]  # (elemento recibido, model nuevo)


def mark_deleted(model: BaseModel, now: datetime, actor_id: UUID) -> None:
    model.is_deleted = True
    model.deleted_at = now
    model.deleted_by = actor_id
    model.updated_at = now
    model.updated_by = actor_id


async def apply_sync[M: BaseModel](
    db_session: AsyncSession,
    *,
    field: str,
    existing: Sequence[M],
    items: Sequence[Any],
    build: Callable[[Any], M],
    now: datetime,
    actor_id: UUID,
    exclude: frozenset[str] = frozenset(),
    before_delete: Callable[[Sequence[M]], Awaitable[None]] | None = None,
) -> AppliedSync[M]:
    """
    existing: las hijas no eliminadas del padre, ya cargadas.
    items: la lista recibida (<Hijo>NestedItem), estado final deseado.
    build: crea el model de un elemento nuevo; el padre lo asigna el service.
    exclude: campos del elemento que no son columnas (por ejemplo, horarios).
    before_delete: comprobación de referencias que bloquean la eliminación (409).

    Un id que no pertenece al padre responde 422 con los ids en details[field].
    """
    try:
        plan = plan_sync([model.id for model in existing], items)
    except ForeignChildError as error:
        raise AppException(
            "Hay elementos que no pertenecen a este registro.",
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            ErrorCode.VALIDATION_ERROR,
            details={field: sorted(map(str, error.ids))},
        ) from error

    by_id = {model.id: model for model in existing}
    deleted = tuple(model for model in existing if model.id in plan.to_delete)
    if deleted and before_delete is not None:
        await before_delete(deleted)
    for model in deleted:
        mark_deleted(model, now, actor_id)

    pending: list[tuple[M, dict[str, Any]]] = []
    for item in plan.to_update:
        model = by_id[item.id]
        values = item.model_dump(exclude={"id", *exclude})
        if any(getattr(model, key) != value for key, value in values.items()):
            model.is_deleted = True  # sale de los índices únicos parciales hasta el segundo flush
            pending.append((model, values))

    await db_session.flush()  # libera los índices: eliminados y filas que cambian

    for model, values in pending:
        for key, value in values.items():
            setattr(model, key, value)
        model.is_deleted = False
        model.updated_at = now
        model.updated_by = actor_id

    created: list[tuple[Any, M]] = []
    for item in plan.to_create:
        model = build(item)
        db_session.add(model)
        created.append((item, model))

    return AppliedSync(
        deleted=deleted,
        updated=tuple((item, by_id[item.id]) for item in plan.to_update),
        created=tuple(created),
    )
