from enum import Enum


class Role(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    USER = "user"


class Module(str, Enum):
    PLAN = "PLAN"
    USUARIO = "USUARIO"
    PAGO = "PAGO"
    TARJETA = "TARJETA"
    TARJETA_THEME = "TARJETA_THEME"
    TARJETA_SEO = "TARJETA_SEO"
    TARJETA_SECCION = "TARJETA_SECCION"
    TARJETA_CONTACTO = "TARJETA_CONTACTO"
    TARJETA_UBICACION = "TARJETA_UBICACION"
    UBICACION_HORARIO = "UBICACION_HORARIO"
    TARJETA_SOCIAL = "TARJETA_SOCIAL"
    TARJETA_EDUCACION = "TARJETA_EDUCACION"
    TARJETA_CERTIFICACION = "TARJETA_CERTIFICACION"
    TARJETA_FAQ = "TARJETA_FAQ"
    VITRINA = "VITRINA"
    VITRINA_CATEGORIA = "VITRINA_CATEGORIA"
    VITRINA_ITEM = "VITRINA_ITEM"
    VITRINA_ITEM_IMAGEN = "VITRINA_ITEM_IMAGEN"
    IMAGEN = "IMAGEN"


class Action(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    AUDIT = "AUDIT"


# Enums de dominio: tipos ENUM de database.md. En PostgreSQL se guarda el valor.

class MetodoPago(str, Enum):
    QR = "qr"
    TRANSFERENCIA = "transferencia"
    TARJETA = "tarjeta"
    EFECTIVO = "efectivo"
    OTRO = "otro"


class PosicionNombreEmpresa(str, Enum):
    ARRIBA = "arriba"
    ABAJO = "abajo"
    IZQUIERDA = "izquierda"
    DERECHA = "derecha"
    OCULTO = "oculto"


class PresetTheme(str, Enum):
    CLARO = "claro"
    OSCURO = "oscuro"
    ELEGANTE = "elegante"
    SALUD = "salud"
    CORPORATIVO = "corporativo"
    CALIDO = "calido"
    NATURAL = "natural"
    BELLEZA = "belleza"
    CREATIVO = "creativo"
    ENERGIA = "energia"


class FormaIcono(str, Enum):
    CIRCULO = "circulo"
    REDONDEADO = "redondeado"
    CUADRADO = "cuadrado"
    NINGUNO = "ninguno"


class PosicionFab(str, Enum):
    DERECHA = "derecha"
    IZQUIERDA = "izquierda"


class ClaveSeccion(str, Enum):
    ACERCA = "acerca"
    CONTACTO = "contacto"
    VITRINA = "vitrina"
    UBICACION = "ubicacion"
    REDES = "redes"
    EDUCACION = "educacion"
    CERTIFICACIONES = "certificaciones"
    FAQ = "faq"


class TipoContacto(str, Enum):
    PHONE = "phone"
    EMAIL = "email"
    WEBSITE = "website"


class RedSocial(str, Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    X = "x"
    THREADS = "threads"
    BLUESKY = "bluesky"
    PINTEREST = "pinterest"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"
    TWITCH = "twitch"
    VIMEO = "vimeo"
    SPOTIFY = "spotify"
    SOUNDCLOUD = "soundcloud"
    MEDIUM = "medium"
    SUBSTACK = "substack"
    GITHUB = "github"
    GITLAB = "gitlab"
    BEHANCE = "behance"
    DRIBBBLE = "dribbble"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    CALENDLY = "calendly"
    DOCTORALIA = "doctoralia"
    OTRO = "otro"
