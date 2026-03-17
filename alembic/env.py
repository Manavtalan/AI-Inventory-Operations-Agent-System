"""
Alembic environment configuration — async-compatible.

Uses settings.database_url (asyncpg) for online migrations via asyncio.
The sync URL path (offline mode) also uses settings values directly.

To add new models to autogenerate:
    from app.models.my_model import MyModel  # noqa: F401
Add the import below the "Model imports" comment.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.models.base import Base

# ---------------------------------------------------------------------------
# Model imports — add each new model module here so its metadata is registered
# ---------------------------------------------------------------------------
# from app.models.shopify_event import ShopifyEvent  # noqa: F401  ← Phase 1
# from app.models.inventory_snapshot import InventorySnapshot  # noqa: F401  ← Phase 2

# ---------------------------------------------------------------------------
# Alembic config
# ---------------------------------------------------------------------------

config = context.config

# Override sqlalchemy.url from settings (ignores the placeholder in alembic.ini)
config.set_main_option("sqlalchemy.url", settings.database_url)

# Logging setup from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live connection)."""
    url = config.get_main_option("sqlalchemy.url")
    # asyncpg is an async-only driver and cannot run in offline (sync) mode
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "+psycopg2")
    context.configure(
        url=url,
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
    """Create an async engine and run migrations within it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # no pooling for migrations
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (requires a live database connection)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
