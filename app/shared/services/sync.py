"""
Plan de sincronización de listas embebidas (AGENTS.md §20 y §22).

En un UpdateNested cada lista es el estado final deseado. Estas funciones solo
calculan qué eliminar, actualizar y crear: no consultan la base ni modifican
nada. El service aplica el plan dentro de su transacción, en este orden:
eliminar, flush(), actualizar y crear.

La validación de ids repetidos dentro de una lista pertenece al schema.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


class HasOptionalId(Protocol):
    id: UUID | None


class ForeignChildError(ValueError):
    """Un elemento trae un id que no pertenece al padre o que está eliminado."""

    def __init__(self, ids: set[UUID]) -> None:
        self.ids = ids
        super().__init__(f"Ids que no pertenecen al registro: {sorted(map(str, ids))}")


@dataclass(frozen=True)
class SyncPlan[T]:
    to_delete: frozenset[UUID]  # existentes que no vinieron en la lista
    to_update: tuple[T, ...]  # elementos con id
    to_create: tuple[T, ...]  # elementos sin id


@dataclass(frozen=True)
class IdsSyncPlan:
    to_delete: frozenset[UUID]  # enlaces existentes que no vinieron
    to_create: frozenset[UUID]  # ids recibidos que todavía no estaban enlazados


def plan_sync[T: HasOptionalId](existing_ids: Iterable[UUID], items: Sequence[T]) -> SyncPlan[T]:
    """
    Plan para una lista de hijas embebidas (<Hijo>NestedItem).

    existing_ids son los hijos no eliminados del padre. Lanza ForeignChildError
    si un elemento trae un id fuera de ese conjunto; el service la convierte en
    un 422.
    """
    existing = set(existing_ids)
    foreign = {item.id for item in items if item.id is not None and item.id not in existing}
    if foreign:
        raise ForeignChildError(foreign)

    received = {item.id for item in items if item.id is not None}
    return SyncPlan(
        to_delete=frozenset(existing - received),
        to_update=tuple(item for item in items if item.id is not None),
        to_create=tuple(item for item in items if item.id is None),
    )


def plan_ids_sync(existing_ids: Iterable[UUID], received_ids: Iterable[UUID]) -> IdsSyncPlan:
    """
    Plan para una lista <relacion>_ids de un Puente N:M.

    Un id que se conserva no aparece en el plan: su enlace no se toca y mantiene
    su auditoría original. Repetir la misma petición produce un plan vacío.
    """
    existing = set(existing_ids)
    received = set(received_ids)
    return IdsSyncPlan(
        to_delete=frozenset(existing - received),
        to_create=frozenset(received - existing),
    )
