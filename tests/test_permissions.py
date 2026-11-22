from app.shared.enums import Action, Module, Role
from app.shared.services.permissions import (
    ROLE_LEVEL,
    ROLE_PERMISSIONS,
    TARJETA_GLOBAL_SCOPE_ROLES,
    TARJETA_OWNER_SCOPE_ROLES,
    can_manage_role,
    has_permission,
)


TARJETA_TREE_MODULES = (
    Module.TARJETA,
    Module.TARJETA_THEME,
    Module.TARJETA_SEO,
    Module.TARJETA_SECCION,
    Module.TARJETA_CONTACTO,
    Module.TARJETA_UBICACION,
    Module.UBICACION_HORARIO,
    Module.TARJETA_SOCIAL,
    Module.TARJETA_EDUCACION,
    Module.TARJETA_CERTIFICACION,
    Module.TARJETA_FAQ,
    Module.VITRINA,
    Module.VITRINA_CATEGORIA,
    Module.VITRINA_ITEM,
    Module.VITRINA_ITEM_IMAGEN,
)


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
    assert has_permission(Role.ADMIN, Module.PAGO, Action.DELETE)
    assert not has_permission(Role.USER, Module.USUARIO, Action.READ)
    assert not has_permission(Role.USER, Module.PAGO, Action.READ)
    assert not has_permission(Role.USER, Module.TARJETA, Action.AUDIT)


def test_filas_fijas_y_kardex_no_admiten_todas_las_acciones():
    for role in Role:
        assert not has_permission(role, Module.PLAN, Action.CREATE)
        assert not has_permission(role, Module.PLAN, Action.DELETE)
        assert not has_permission(role, Module.PAGO, Action.UPDATE)


def test_la_tarjeta_solo_la_crea_su_duenio():
    assert has_permission(Role.USER, Module.TARJETA, Action.CREATE)
    assert not has_permission(Role.ADMIN, Module.TARJETA, Action.CREATE)
    assert not has_permission(Role.SUPERADMIN, Module.TARJETA, Action.CREATE)


def test_jerarquia_estricta():
    assert can_manage_role(Role.SUPERADMIN, Role.ADMIN)
    assert can_manage_role(Role.SUPERADMIN, Role.USER)
    assert can_manage_role(Role.ADMIN, Role.USER)
    assert not can_manage_role(Role.ADMIN, Role.ADMIN)
    assert not can_manage_role(Role.ADMIN, Role.SUPERADMIN)
    assert not can_manage_role(Role.USER, Role.USER)


def test_los_grupos_de_alcance_de_la_tarjeta_no_se_solapan():
    assert not TARJETA_GLOBAL_SCOPE_ROLES & TARJETA_OWNER_SCOPE_ROLES


def test_todo_rol_con_acceso_a_la_tarjeta_tiene_alcance():
    scoped_roles = TARJETA_GLOBAL_SCOPE_ROLES | TARJETA_OWNER_SCOPE_ROLES
    for role, modules in ROLE_PERMISSIONS.items():
        if any(modules[module] for module in TARJETA_TREE_MODULES):
            assert role in scoped_roles, role
