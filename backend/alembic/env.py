"""
============================================================================
AutoTwin AI - Alembic Migration Environment
============================================================================
Configures Alembic to work with SQLAlchemy async engine and FastAPI models.

This file is executed by Alembic during migration operations.
It sets up the database connection and model metadata.
============================================================================
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ============================================================================
# ALEMBIC CONFIG
# ============================================================================

# Alembic Config object (provides access to values in alembic.ini)
config = context.config

# Set up Python logging from the config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ============================================================================
# MODEL METADATA
# ============================================================================

# Import all SQLAlchemy models so Alembic can detect them for autogenerate.
# This MUST import the Base and all model classes.

import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import Base
from app.db import models  # noqa: F401 — Import all models for metadata

# Set the target metadata for autogenerate support
target_metadata = Base.metadata

# ============================================================================
# OFFLINE MIGRATIONS (generate SQL without DB connection)
# ============================================================================


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL script without connecting to the database.
    Useful for reviewing migrations before applying.

    Usage: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================================
# ONLINE MIGRATIONS (apply to live database)
# ============================================================================


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations using a synchronous connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode with async engine.

    Creates an async engine and associates a connection with the context.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations."""
    # Check if we're using async driver
    url = config.get_main_option("sqlalchemy.url")

    if url and ("aiosqlite" in url or "asyncpg" in url):
        # Async path
        asyncio.run(run_async_migrations())
    else:
        # Sync path (standard sqlite:/// or postgresql://)
        from sqlalchemy import create_engine

        connectable = create_engine(
            url,
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            do_run_migrations(connection)

        connectable.dispose()


# ============================================================================
# ENTRY POINT
# ============================================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()