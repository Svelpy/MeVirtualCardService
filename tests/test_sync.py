from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from app.shared.services.sync import ForeignChildError, plan_ids_sync, plan_sync


class Item(BaseModel):
    id: UUID | None = None
    cantidad: int = 1


def test_actualiza_crea_y_elimina():
    a, b, c = uuid4(), uuid4(), uuid4()
    nuevo = Item(cantidad=3)
    plan = plan_sync({a, b, c}, [Item(id=a), nuevo])

    assert plan.to_update == (Item(id=a),)
    assert plan.to_create == (nuevo,)
    assert plan.to_delete == frozenset({b, c})


def test_lista_vacia_elimina_todo():
    a, b = uuid4(), uuid4()
    plan = plan_sync({a, b}, [])
    assert plan.to_delete == frozenset({a, b})
    assert plan.to_update == plan.to_create == ()


def test_id_ajeno_se_rechaza():
    ajeno = uuid4()
    with pytest.raises(ForeignChildError) as error:
        plan_sync({uuid4()}, [Item(id=ajeno)])
    assert error.value.ids == {ajeno}


def test_ids_conservados_no_aparecen_en_el_plan():
    a, b, c = uuid4(), uuid4(), uuid4()
    plan = plan_ids_sync({a, c}, [a, b])
    assert plan.to_delete == frozenset({c})
    assert plan.to_create == frozenset({b})


def test_repetir_la_misma_peticion_no_produce_cambios():
    a, b = uuid4(), uuid4()
    plan = plan_ids_sync({a, b}, [a, b])
    assert plan.to_delete == plan.to_create == frozenset()
