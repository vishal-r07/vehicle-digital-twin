"""
============================================================================
AutoTwin AI - Database Module
============================================================================
Async SQLAlchemy database layer with SQLite (Phase 1) and
PostgreSQL migration path (Phase 2+).

Components:
  - database.py:     Engine, session factory, base model
  - models.py:       ORM model definitions
  - repositories.py: Data access layer (repository pattern)

Database: SQLite (Phase 1) → PostgreSQL (Phase 2+)
Driver:   aiosqlite (async) → asyncpg (async)
ORM:      SQLAlchemy 2.0+ with async support
Migration: Alembic

Usage:
    from app.db import get_session, Vehicle, FaultEventRepository

    async with get_session() as session:
        repo = FaultEventRepository(session)
        faults = await repo.get_active()
============================================================================
"""

from app.db.database import (  # noqa: F401
    Base,
    get_engine,
    get_async_session_factory,
    get_session,
    init_db,
    close_db,
)
from app.db.models import (  # noqa: F401
    Vehicle,
    VehicleProfile,
    FaultEventModel,
    TimelineEventModel,
    HealthSnapshotModel,
    CANLogModel,
    ScenarioModel,
    ScenarioRunModel,
    SystemConfigModel,
)
from app.db.repositories import (  # noqa: F401
    VehicleRepository,
    FaultEventRepository,
    TimelineRepository,
    HealthSnapshotRepository,
    CANLogRepository,
    ScenarioRepository,
    SystemConfigRepository,
)

__all__ = [
    "Base",
    "get_engine",
    "get_async_session_factory",
    "get_session",
    "init_db",
    "close_db",
    "Vehicle",
    "VehicleProfile",
    "FaultEventModel",
    "TimelineEventModel",
    "HealthSnapshotModel",
    "CANLogModel",
    "ScenarioModel",
    "ScenarioRunModel",
    "SystemConfigModel",
    "VehicleRepository",
    "FaultEventRepository",
    "TimelineRepository",
    "HealthSnapshotRepository",
    "CANLogRepository",
    "ScenarioRepository",
    "SystemConfigRepository",
]