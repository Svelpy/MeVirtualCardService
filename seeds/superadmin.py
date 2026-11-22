"""
Crea los 3 superadmins: el rol de mayor rango no se puede crear desde la API
(AGENTS.md §24), así que nace de este seed.

Uso, a mano:

    python -m seeds.superadmin

Lee SEED_SUPERADMIN_{1,2,3}_EMAIL y SEED_SUPERADMIN_{1,2,3}_PASSWORD. Valida los
tres antes de escribir nada y los crea en una sola transacción, con el email
verificado. Se puede repetir: un email que ya existe se deja como está.
"""

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.config import Settings, get_settings
from app.core.database import close_database, initialize_database
from app.domains.usuario.repositories import UsuarioRepository
from app.domains.usuario.services import UsuarioService
from app.shared.enums import Role
from app.shared.services.validators import validator_email, validator_password


def read_superadmins(settings: Settings) -> list[tuple[str, str]]:
    """(email, password) de los 3 superadmins, validados. Lanza SystemExit si falta o sobra algo."""
    superadmins: list[tuple[str, str]] = []
    errors: list[str] = []
    for number, (email, password) in enumerate(settings.SEED_SUPERADMINS, start=1):
        prefix = f"SEED_SUPERADMIN_{number}"
        if not email or password is None:
            errors.append(f"Faltan {prefix}_EMAIL o {prefix}_PASSWORD.")
            continue
        try:
            superadmins.append((validator_email(email), validator_password(password.get_secret_value())))
        except ValueError as error:
            errors.append(f"{prefix}: {error}")
    emails = [email for email, _ in superadmins]
    if len(emails) != len(set(emails)):
        errors.append("Los 3 superadmins deben tener emails distintos.")
    if errors:
        raise SystemExit("\n".join(errors))
    return superadmins


async def seed_superadmins(db_session: AsyncSession, superadmins: list[tuple[str, str]]) -> list[str]:
    """Crea los que no existen y devuelve sus emails. Hace commit."""
    created: list[str] = []
    for email, password in superadmins:
        if await UsuarioRepository.get_by_email(db_session, email) is not None:
            continue
        usuario = await UsuarioService.add_new(
            db_session, email=email, password=password, rol=Role.SUPERADMIN, created_by=None
        )
        usuario.email_verified_at = utc_now()
        created.append(email)
    await db_session.commit()
    return created


async def main() -> None:
    settings = get_settings()
    superadmins = read_superadmins(settings)
    engine, session_factory = initialize_database(settings)
    try:
        async with session_factory() as db_session:
            created = await seed_superadmins(db_session, superadmins)
    finally:
        await close_database(engine)
    for email, _ in superadmins:
        print(f"{'Creado' if email in created else 'Ya existía'}: {email}")


if __name__ == "__main__":
    asyncio.run(main())
