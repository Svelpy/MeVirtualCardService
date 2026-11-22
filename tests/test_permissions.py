from app.shared.enums import Action, Module, Role
from app.shared.services.permissions import ROLE_LEVEL, ROLE_PERMISSIONS, can_manage_role, has_permission


def test_todo_rol_tiene_nivel_y_fila_en_la_matriz():
    assert set(ROLE_LEVEL) == set(Role)
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_cada_rol_lista_todos_los_modulos():
    for role, modules in ROLE_PERMISSIONS.items():
        assert set(modules) == set(Module), role


def test_los_accesos_son_frozenset():
    for modules in ROLE_PERMISSIONS.values():
        for actions in modules.values():
            assert isinstance(actions, frozenset)


def test_has_permission():
    assert has_permission(Role.SUPERADMIN, Module.USUARIO, Action.AUDIT)
    assert not has_permission(Role.ADMIN, Module.USUARIO, Action.CREATE)


def test_jerarquia_estricta():
    assert can_manage_role(Role.SUPERADMIN, Role.ADMIN)
    assert not can_manage_role(Role.ADMIN, Role.ADMIN)
    assert not can_manage_role(Role.ADMIN, Role.SUPERADMIN)
