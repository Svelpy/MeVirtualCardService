"""Entorno de Alembic: usa la misma base que la aplicación (AGENTS.md §7 y §8)."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

# Todo models.py se importa aquí: un model que no se importa no existe para
# Alembic, y autogenerate propondría eliminar su tabla. Un import por dominio.
import app.domains.error_logs.models  # noqa: F401
from app.core.config import get_settings
from app.core.database import _get_database_url, get_connect_args

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

# La misma selección por ENVIRONMENT que la aplicación.
DATABASE_URL = _get_database_url(get_settings())


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (alembic upgrade head --sql)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        DATABASE_URL,
        poolclass=pool.NullPool,
        connect_args=get_connect_args(),
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
