"""
============================================================================
AutoTwin AI - Database Setup & Session Management
============================================================================
Async SQLAlchemy engine and session configuration.

Phase 1: SQLite via aiosqlite (zero-config, single file)
Phase 2: PostgreSQL via asyncpg (multi-user, concurrent)

The database URL is configured in app/config.py:
  DATABASE_URL=sqlite:///./autotwin.db

Session Pattern:
  Sessions are managed via async context managers.
  Each request gets its own session (dependency injection).
  Sessions auto-commit on success, rollback on exception.

Usage:
    # In FastAPI dependency:
    async def get_db():
        async with get_session() as session:
            yield session

    # Direct usage:
    async with get_session() as session:
        result = await session.execute(select(Vehicle))
============================================================================
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from loguru import logger
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


# ============================================================================
# BASE MODEL
# ============================================================================


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    All models inherit from this to get:
      - Table metadata registration
      - Relationship resolution
      - Alembic autogenerate support
    """

    pass


# ============================================================================
# ENGINE & SESSION FACTORY (Module-level singletons)
# ============================================================================

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker] = None


def get_engine() -> AsyncEngine:
    """
    Get or create the async database engine.

    Creates the engine on first call (singleton pattern).
    Thread-safe due to GIL.

    Returns:
        AsyncEngine instance.
    """
    global _engine

    if _engine is None:
        settings = get_settings()
        db_url = settings.database.async_url

        logger.info(f"Database: creating engine ({db_url.split(':///')[0]})")

        # Engine configuration
        engine_kwargs = {
            "echo": settings.database.echo,
            "pool_pre_ping": True,
        }

        # SQLite-specific settings
        if settings.database.is_sqlite:
            engine_kwargs["connect_args"] = {
                "check_same_thread": False,  # Allow multi-thread access
            }
        else:
            # PostgreSQL connection pool settings
            engine_kwargs["pool_size"] = settings.database.pool_size
            engine_kwargs["max_overflow"] = settings.database.max_overflow
            engine_kwargs["pool_timeout"] = settings.database.pool_timeout

        _engine = create_async_engine(db_url, **engine_kwargs)

        # Register SQLite pragmas for performance
        if settings.database.is_sqlite:
            @_event.listens_for(_engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")       # Write-Ahead Logging
                cursor.execute("PRAGMA synchronous=NORMAL")     # Balanced durability
                cursor.execute("PRAGMA cache_size=-64000")      # 64MB cache
                cursor.execute("PRAGMA foreign_keys=ON")        # Enforce FK constraints
                cursor.execute("PRAGMA busy_timeout=5000")      # 5s lock timeout
                cursor.close()

    return _engine


def get_async_session_factory() -> async_sessionmaker:
    """
    Get or create the async session factory.

    Returns:
        async_sessionmaker configured for the current engine.
    """
    global _session_factory

    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Prevent lazy-load after commit
            autoflush=False,         # Manual flush control
        )

    return _session_factory


# ============================================================================
# SESSION CONTEXT MANAGER
# ============================================================================


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.

    Provides automatic commit/rollback/close:
      - Commits on successful exit
      - Rolls back on exception
      - Always closes the session

    Usage:
        async with get_session() as session:
            session.add(new_vehicle)
            # Auto-commits on exit

    Yields:
        AsyncSession instance.
    """
    factory = get_async_session_factory()
    session = factory()

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ============================================================================
# FASTAPI DEPENDENCY
# ============================================================================


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Usage in endpoints:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_db_session)):
            ...

    Yields:
        AsyncSession instance.
    """
    factory = get_async_session_factory()
    session = factory()

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ============================================================================
# DATABASE LIFECYCLE
# ============================================================================


async def init_db() -> None:
    """
    Initialize the database.

    Creates tables if they don't exist (for development).
    In production, use Alembic migrations instead.

    Called during application startup.
    """
    engine = get_engine()
    settings = get_settings()

    logger.info("Database: initializing...")

    # Import all models to register them with Base.metadata
    from app.db import models  # noqa: F401

    # Create tables (development only — use Alembic in production)
    if settings.app.debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database: tables created (debug mode)")
    else:
        # Verify tables exist (don't create in production)
        async with engine.begin() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
                if settings.database.is_sqlite
                else text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            )
            tables = [row[0] for row in result.fetchall()]

        if not tables:
            logger.warning(
                "Database: no tables found. Run 'alembic upgrade head' to create schema."
            )

    logger.info("Database: initialization complete")


async def close_db() -> None:
    """
    Close the database engine and release connections.

    Called during application shutdown.
    """
    global _engine, _session_factory

    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database: engine closed")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


async def check_connection() -> bool:
    """
    Verify database connectivity.

    Returns:
        True if connection successful.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database: connection check failed: {e}")
        return False


async def get_table_count() -> int:
    """Get number of tables in the database."""
    try:
        engine = get_engine()
        settings = get_settings()

        async with engine.connect() as conn:
            if settings.database.is_sqlite:
                result = await conn.execute(
                    text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                )
            else:
                result = await conn.execute(
                    text("SELECT COUNT(*) FROM pg_tables WHERE schemaname='public'")
                )
            return result.scalar() or 0
    except Exception:
        return 0