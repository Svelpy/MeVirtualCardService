"""Seed de los 3 superadmins (seeds/superadmin.py)."""

import pytest

from app.domains.usuario.repositories import UsuarioRepository
from app.shared.enums import Role
from seeds.superadmin import read_superadmins, seed_superadmins
from tests.conftest import make_settings


def _settings(**overrides: object):
    values = {}
    for number in (1, 2, 3):
        values[f"SEED_SUPERADMIN_{number}_EMAIL"] = f" Super{number}@Test.Example.com "
        values[f"SEED_SUPERADMIN_{number}_PASSWORD"] = f"ClaveSegura{number}23"
    values.update(overrides)
    return make_settings(**values)


def test_lee_y_normaliza_los_tres():
    assert [email for email, _ in read_superadmins(_settings())] == [
        "super1@test.example.com",
        "super2@test.example.com",
        "super3@test.example.com",
    ]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"SEED_SUPERADMIN_2_EMAIL": None}, "Faltan SEED_SUPERADMIN_2_EMAIL"),
        ({"SEED_SUPERADMIN_3_PASSWORD": "corta"}, "SEED_SUPERADMIN_3: La contraseña debe tener al menos 8"),
        ({"SEED_SUPERADMIN_2_EMAIL": "super1@test.example.com"}, "emails distintos"),
    ],
)
def test_no_escribe_nada_si_falta_o_sobra_algo(overrides, message):
    with pytest.raises(SystemExit, match=message):
        read_superadmins(_settings(**overrides))


async def test_crea_los_tres_verificados_y_repetirlo_no_duplica(db_session):
    superadmins = read_superadmins(_settings())
    assert len(await seed_superadmins(db_session, superadmins)) == 3
    for email, _ in superadmins:
        usuario = await UsuarioRepository.get_by_email(db_session, email)
        assert usuario.rol == Role.SUPERADMIN and usuario.email_verified_at is not None
    assert await seed_superadmins(db_session, superadmins) == []
