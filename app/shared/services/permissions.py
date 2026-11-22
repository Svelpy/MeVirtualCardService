"""
Única fuente de verdad de "quién puede hacer qué, sobre qué módulo" (AGENTS.md §24).

Agregar un rol exige declararlo en Role (shared/enums.py) y actualizar todas las
estructuras de este archivo. Agregar un módulo exige declararlo en Module y
añadirlo a la fila de cada rol.

Lo que una hija embebida o una extensión 1:1 hace dentro de su padre lo autoriza
el permiso del padre (por ejemplo, TARJETA + UPDATE). Su propio módulo solo
cubre sus rutas propias, su /audit y sus endpoints de acción.
"""

from app.shared.enums import Action, Module, Role


# Cada rol lista todos los módulos, para que la matriz se lea como una tabla.
# frozenset() == sin acceso a ese módulo. Un rol o módulo ausente también
# equivale a sin acceso.
ROLE_PERMISSIONS: dict[Role, dict[Module, frozenset[Action]]] = {
    Role.SUPERADMIN: {
        Module.PLAN: frozenset({Action.READ, Action.UPDATE, Action.AUDIT}),  # filas fijas: no se crean ni se eliminan
        Module.USUARIO: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),
        Module.PAGO: frozenset({Action.CREATE, Action.READ, Action.DELETE, Action.AUDIT}),  # kardex: no se edita; DELETE = anular
        Module.TARJETA: frozenset({Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),  # la tarjeta la crea su dueño
        Module.TARJETA_THEME: frozenset({Action.READ, Action.UPDATE, Action.AUDIT}),  # se crea y elimina con la tarjeta
        Module.TARJETA_SEO: frozenset({Action.READ, Action.UPDATE, Action.AUDIT}),  # se crea y elimina con la tarjeta
        Module.TARJETA_SECCION: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_CONTACTO: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_UBICACION: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.UBICACION_HORARIO: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_SOCIAL: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_EDUCACION: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_CERTIFICACION: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_FAQ: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.VITRINA: frozenset({Action.READ, Action.UPDATE, Action.AUDIT}),  # se crea y elimina con la tarjeta
        Module.VITRINA_CATEGORIA: frozenset({Action.AUDIT}),  # se edita desde la vitrina
        Module.VITRINA_ITEM: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),
        Module.VITRINA_ITEM_IMAGEN: frozenset({Action.AUDIT}),  # se edita desde el item
        Module.IMAGEN: frozenset({Action.CREATE}),  # solo subir imágenes pendientes
    },
    Role.ADMIN: {
        Module.PLAN: frozenset({Action.READ, Action.UPDATE, Action.AUDIT}),  # filas fijas: no se crean ni se eliminan
        # La jerarquía (can_manage_role) limita la gestión a usuarios de rol inferior.
        Module.USUARIO: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),
        Module.PAGO: frozenset({Action.CREATE, Action.READ, Action.DELETE, Action.AUDIT}),  # kardex: no se edita; DELETE = anular
        Module.TARJETA: frozenset({Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),  # la tarjeta la crea su dueño
        Module.TARJETA_THEME: frozenset({Action.READ, Action.UPDATE, Action.AUDIT}),  # se crea y elimina con la tarjeta
        Module.TARJETA_SEO: frozenset({Action.READ, Action.UPDATE, Action.AUDIT}),  # se crea y elimina con la tarjeta
        Module.TARJETA_SECCION: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_CONTACTO: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_UBICACION: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.UBICACION_HORARIO: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_SOCIAL: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_EDUCACION: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_CERTIFICACION: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.TARJETA_FAQ: frozenset({Action.AUDIT}),  # se edita desde la tarjeta
        Module.VITRINA: frozenset({Action.READ, Action.UPDATE, Action.AUDIT}),  # se crea y elimina con la tarjeta
        Module.VITRINA_CATEGORIA: frozenset({Action.AUDIT}),  # se edita desde la vitrina
        Module.VITRINA_ITEM: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE, Action.AUDIT}),
        Module.VITRINA_ITEM_IMAGEN: frozenset({Action.AUDIT}),  # se edita desde el item
        Module.IMAGEN: frozenset({Action.CREATE}),  # solo subir imágenes pendientes
    },
    Role.USER: {
        Module.PLAN: frozenset(),  # los consulta en la lectura pública
        Module.USUARIO: frozenset(),  # su perfil lo gestiona desde /me
        Module.PAGO: frozenset(),  # no ve sus pagos: los registra y consulta un admin
        Module.TARJETA: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),  # sin AUDIT: expone datos internos
        Module.TARJETA_THEME: frozenset({Action.READ, Action.UPDATE}),  # se crea y elimina con la tarjeta; sin AUDIT
        Module.TARJETA_SEO: frozenset({Action.READ, Action.UPDATE}),  # se crea y elimina con la tarjeta; sin AUDIT
        Module.TARJETA_SECCION: frozenset(),  # se edita desde la tarjeta; sin AUDIT
        Module.TARJETA_CONTACTO: frozenset(),  # se edita desde la tarjeta; sin AUDIT
        Module.TARJETA_UBICACION: frozenset(),  # se edita desde la tarjeta; sin AUDIT
        Module.UBICACION_HORARIO: frozenset(),  # se edita desde la tarjeta; sin AUDIT
        Module.TARJETA_SOCIAL: frozenset(),  # se edita desde la tarjeta; sin AUDIT
        Module.TARJETA_EDUCACION: frozenset(),  # se edita desde la tarjeta; sin AUDIT
        Module.TARJETA_CERTIFICACION: frozenset(),  # se edita desde la tarjeta; sin AUDIT
        Module.TARJETA_FAQ: frozenset(),  # se edita desde la tarjeta; sin AUDIT
        Module.VITRINA: frozenset({Action.READ, Action.UPDATE}),  # se crea y elimina con la tarjeta; sin AUDIT
        Module.VITRINA_CATEGORIA: frozenset(),  # se edita desde la vitrina; sin AUDIT
        Module.VITRINA_ITEM: frozenset({Action.CREATE, Action.READ, Action.UPDATE, Action.DELETE}),  # sin AUDIT
        Module.VITRINA_ITEM_IMAGEN: frozenset(),  # se edita desde el item; sin AUDIT
        Module.IMAGEN: frozenset({Action.CREATE}),  # solo subir imágenes pendientes
    },
}


# Jerarquía de roles: un número mayor es un rango superior.
# Todo rol de Role debe figurar aquí.
ROLE_LEVEL: dict[Role, int] = {
    Role.USER: 1,
    Role.ADMIN: 2,
    Role.SUPERADMIN: 3,
}


# Alcance de la tarjeta y de todo su árbol (theme, SEO, vitrina, hijas e items).
# Todo rol con acceso a esos módulos pertenece a exactamente un grupo.
TARJETA_GLOBAL_SCOPE_ROLES: frozenset[Role] = frozenset({Role.SUPERADMIN, Role.ADMIN})  # todas las tarjetas
TARJETA_OWNER_SCOPE_ROLES: frozenset[Role] = frozenset({Role.USER})  # solo la tarjeta propia


def has_permission(role: Role, module: Module, action: Action) -> bool:
    """True si el rol tiene la acción habilitada en ese módulo."""
    return action in ROLE_PERMISSIONS.get(role, {}).get(module, frozenset())


def can_manage_role(actor_role: Role, target_role: Role) -> bool:
    """True si actor_role es estrictamente superior a target_role."""
    return ROLE_LEVEL[target_role] < ROLE_LEVEL[actor_role]
