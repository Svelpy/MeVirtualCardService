"""
Única fuente de verdad de "quién puede hacer qué, sobre qué módulo" (AGENTS.md §24).

Agregar un rol exige declararlo en Role (shared/enums.py) y actualizar todas las
estructuras de este archivo. Agregar un módulo exige declararlo en Module y
añadirlo a la fila de cada rol.
"""

from app.shared.enums import Action, Module, Role


# Cada rol lista todos los módulos, para que la matriz se lea como una tabla.
# frozenset() == sin acceso a ese módulo. Un rol o módulo ausente también
# equivale a sin acceso.
ROLE_PERMISSIONS: dict[Role, dict[Module, frozenset[Action]]] = {
    Role.SUPERADMIN: {
        Module.USUARIO: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),
    },
    Role.ADMIN: {
        Module.USUARIO: frozenset({Action.READ}),  # no hay rol inferior que gestionar; su perfil lo edita desde /me
    },
}


# Jerarquía de roles: un número mayor es un rango superior.
# Todo rol de Role debe figurar aquí.
ROLE_LEVEL: dict[Role, int] = {
    Role.ADMIN: 1,
    Role.SUPERADMIN: 2,
}


def has_permission(role: Role, module: Module, action: Action) -> bool:
    """True si el rol tiene la acción habilitada en ese módulo."""
    return action in ROLE_PERMISSIONS.get(role, {}).get(module, frozenset())


def can_manage_role(actor_role: Role, target_role: Role) -> bool:
    """True si actor_role es estrictamente superior a target_role."""
    return ROLE_LEVEL[target_role] < ROLE_LEVEL[actor_role]
