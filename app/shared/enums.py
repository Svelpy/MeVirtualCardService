from enum import Enum


class Role(str, Enum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"


class Module(str, Enum):
    USUARIO = "USUARIO"


class Action(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    AUDIT = "AUDIT"
