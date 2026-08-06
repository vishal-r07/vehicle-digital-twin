"""
============================================================================
AutoTwin AI - Data Access Layer (Repository Pattern)
============================================================================
Encapsulates all database queries behind repository classes.

Benefits:
  - Endpoints never write raw SQLAlchemy queries
  - Easy to test (mock repositories)
  - Single place to optimize queries
  - Consistent error handling

Pattern:
  Each model has a corresponding repository.
  Repositories receive a session via constructor injection.
  All methods are async.

Usage:
    async with get_session() as session:
        repo = FaultEventRepository(session)
        faults = await repo.get_active(limit=50)
        await repo.create(fault_data)
============================================================================
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
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


# ============================================================================
# BASE REPOSITORY
# ============================================================================


class BaseRepository:
    """Base repository with common operations."""

    model = None  # Override in subclasses

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: int) -> Optional[Any]:
        """Get entity by primary key."""
        return await self._session.get(self.model, id)

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[Any]:
        """Get all entities with pagination."""
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Count total entities."""
        stmt = select(func.count()).select_from(self.model)
        result = await self._session.execute(stmt)
        return result.scalar() or 0

    async def delete_by_id(self, id: int) -> bool:
        """Delete entity by ID."""
        entity = await self.get_by_id(id)
        if entity:
            await self._session.delete(entity)
            return True
        return False


# ============================================================================
# VEHICLE REPOSITORY
# ============================================================================


class VehicleRepository(BaseRepository):
    """Data access for Vehicle and VehicleProfile."""

    model = Vehicle

    async def get_by_slug(self, slug: str) -> Optional[Vehicle]:
        """Get vehicle by slug identifier."""
        stmt = select(Vehicle).where(Vehicle.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active(self) -> Optional[Vehicle]:
        """Get the currently active vehicle."""
        stmt = select(Vehicle).where(Vehicle.is_active == True).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_active(self, slug: str) -> Optional[Vehicle]:
        """Set a vehicle as active (deactivates all others)."""
        # Deactivate all
        stmt = update(Vehicle).values(is_active=False)
        await self._session.execute(stmt)

        # Activate target
        vehicle = await self.get_by_slug(slug)
        if vehicle:
            vehicle.is_active = True
            await self._session.flush()
        return vehicle

    async def create(self, data: Dict[str, Any]) -> Vehicle:
        """Create a new vehicle entry."""
        vehicle = Vehicle(
            slug=data["slug"],
            name=data["name"],
            make=data["make"],
            model=data["model"],
            year=data.get("year"),
            category=data.get("category"),
            engine_type=data.get("engine_type"),
            transmission_type=data.get("transmission_type"),
        )
        self._session.add(vehicle)
        await self._session.flush()
        return vehicle

    async def get_with_profile(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get vehicle with its profile data."""
        vehicle = await self.get_by_slug(slug)
        if not vehicle:
            return None

        profile_stmt = select(VehicleProfile).where(
            VehicleProfile.vehicle_id == vehicle.id
        )
        result = await self._session.execute(profile_stmt)
        profile = result.scalar_one_or_none()

        return {
            "vehicle": vehicle.to_dict(),
            "profile": profile.to_dict() if profile else None,
        }

    async def list_all(self) -> List[Dict[str, Any]]:
        """List all vehicles as dictionaries."""
        vehicles = await self.get_all(limit=100)
        return [v.to_dict() for v in vehicles]


# ============================================================================
# FAULT EVENT REPOSITORY
# ============================================================================


class FaultEventRepository(BaseRepository):
    """Data access for FaultEventModel."""

    model = FaultEventModel

    async def get_active(
        self,
        limit: int = 50,
        severity: Optional[str] = None,
        subsystem: Optional[str] = None,
    ) -> List[FaultEventModel]:
        """Get all unresolved (active) faults."""
        stmt = select(FaultEventModel).where(FaultEventModel.resolved == False)

        if severity:
            stmt = stmt.where(FaultEventModel.severity == severity)
        if subsystem:
            stmt = stmt.where(FaultEventModel.subsystem == subsystem)

        stmt = stmt.order_by(FaultEventModel.priority.asc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_fault_id(self, fault_id: str) -> Optional[FaultEventModel]:
        """Get fault by unique fault_id."""
        stmt = select(FaultEventModel).where(FaultEventModel.fault_id == fault_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_history(
        self,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[FaultEventModel]:
        """Get fault history with optional date filtering."""
        stmt = select(FaultEventModel).order_by(
            FaultEventModel.created_at.desc()
        )

        if start_date:
            stmt = stmt.where(FaultEventModel.created_at >= start_date)
        if end_date:
            stmt = stmt.where(FaultEventModel.created_at <= end_date)

        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: Dict[str, Any]) -> FaultEventModel:
        """Create a new fault event record."""
        fault = FaultEventModel(
            fault_id=data.get("fault_id", f"F-{uuid.uuid4().hex[:8].upper()}"),
            vehicle_id=data.get("vehicle_id"),
            rule_id=data["rule_id"],
            severity=data["severity"],
            confidence=data.get("confidence", 0.8),
            message=data["message"],
            signal_values=json.dumps(data.get("signal_values", {})),
            possible_causes=json.dumps(data.get("possible_causes", [])),
            recommendation=data.get("recommendation", ""),
            estimated_repair_time=data.get("estimated_repair_time", ""),
            priority=data.get("priority", 3),
            subsystem=data.get("subsystem", ""),
        )
        self._session.add(fault)
        await self._session.flush()
        return fault

    async def resolve(self, fault_id: str, reason: str = "auto") -> bool:
        """Mark a fault as resolved."""
        stmt = (
            update(FaultEventModel)
            .where(FaultEventModel.fault_id == fault_id)
            .values(
                resolved=True,
                resolved_at=datetime.now(timezone.utc),
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def acknowledge(self, fault_id: str) -> bool:
        """Mark a fault as acknowledged."""
        stmt = (
            update(FaultEventModel)
            .where(FaultEventModel.fault_id == fault_id)
            .values(acknowledged=True)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get fault statistics."""
        total = await self.count()

        active_stmt = select(func.count()).where(FaultEventModel.resolved == False)
        active_result = await self._session.execute(active_stmt)
        active = active_result.scalar() or 0

        return {
            "total": total,
            "active": active,
            "resolved": total - active,
        }


# ============================================================================
# TIMELINE REPOSITORY
# ============================================================================


class TimelineRepository(BaseRepository):
    """Data access for TimelineEventModel."""

    model = TimelineEventModel

    async def get_recent(self, limit: int = 100) -> List[TimelineEventModel]:
        """Get most recent timeline events."""
        stmt = (
            select(TimelineEventModel)
            .order_by(TimelineEventModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_type(self, event_type: str, limit: int = 100) -> List[TimelineEventModel]:
        """Get events filtered by type."""
        stmt = (
            select(TimelineEventModel)
            .where(TimelineEventModel.event_type == event_type)
            .order_by(TimelineEventModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_between(
        self, start: datetime, end: datetime, limit: int = 500
    ) -> List[TimelineEventModel]:
        """Get events within a time range."""
        stmt = (
            select(TimelineEventModel)
            .where(
                TimelineEventModel.created_at >= start,
                TimelineEventModel.created_at <= end,
            )
            .order_by(TimelineEventModel.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: Dict[str, Any]) -> TimelineEventModel:
        """Create a new timeline event."""
        entry = TimelineEventModel(
            vehicle_id=data.get("vehicle_id"),
            event_type=data["event_type"],
            severity=data.get("severity", "INFO"),
            message=data["message"],
            signal_name=data.get("signal_name", ""),
            signal_value=data.get("signal_value"),
            metadata=json.dumps(data.get("metadata", {})),
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def cleanup(self, max_entries: int = 10000) -> int:
        """Remove oldest entries beyond max_entries."""
        count = await self.count()
        if count <= max_entries:
            return 0

        # Get IDs of entries to delete
        stmt = (
            select(TimelineEventModel.id)
            .order_by(TimelineEventModel.created_at.asc())
            .limit(count - max_entries)
        )
        result = await self._session.execute(stmt)
        ids_to_delete = [row[0] for row in result.fetchall()]

        if ids_to_delete:
            stmt = delete(TimelineEventModel).where(TimelineEventModel.id.in_(ids_to_delete))
            await self._session.execute(stmt)

        return len(ids_to_delete)


# ============================================================================
# HEALTH SNAPSHOT REPOSITORY
# ============================================================================


class HealthSnapshotRepository(BaseRepository):
    """Data access for HealthSnapshotModel."""

    model = HealthSnapshotModel

    async def get_recent(
        self, vehicle_id: int, limit: int = 100
    ) -> List[HealthSnapshotModel]:
        """Get recent health snapshots for a vehicle."""
        stmt = (
            select(HealthSnapshotModel)
            .where(HealthSnapshotModel.vehicle_id == vehicle_id)
            .order_by(HealthSnapshotModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_between(
        self, vehicle_id: int, start: datetime, end: datetime
    ) -> List[HealthSnapshotModel]:
        """Get snapshots within a time range."""
        stmt = (
            select(HealthSnapshotModel)
            .where(
                HealthSnapshotModel.vehicle_id == vehicle_id,
                HealthSnapshotModel.created_at >= start,
                HealthSnapshotModel.created_at <= end,
            )
            .order_by(HealthSnapshotModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: Dict[str, Any]) -> HealthSnapshotModel:
        """Store a new health snapshot."""
        snapshot = HealthSnapshotModel(
            vehicle_id=data["vehicle_id"],
            overall_score=data["overall_score"],
            engine_score=data.get("engine_score"),
            battery_score=data.get("battery_score"),
            brake_score=data.get("brake_score"),
            cooling_score=data.get("cooling_score"),
            transmission_score=data.get("transmission_score"),
            electrical_score=data.get("electrical_score"),
            active_fault_count=data.get("active_fault_count", 0),
        )
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot

    async def get_latest(self, vehicle_id: int) -> Optional[HealthSnapshotModel]:
        """Get the most recent snapshot."""
        stmt = (
            select(HealthSnapshotModel)
            .where(HealthSnapshotModel.vehicle_id == vehicle_id)
            .order_by(HealthSnapshotModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()


# ============================================================================
# CAN LOG REPOSITORY
# ============================================================================


class CANLogRepository(BaseRepository):
    """Data access for CANLogModel (replay recordings)."""

    model = CANLogModel

    async def get_sessions(self) -> List[Dict[str, Any]]:
        """Get list of recorded sessions."""
        stmt = (
            select(
                CANLogModel.session_id,
                func.count(CANLogModel.id).label("frame_count"),
                func.min(CANLogModel.created_at).label("started_at"),
                func.max(CANLogModel.created_at).label("ended_at"),
            )
            .group_by(CANLogModel.session_id)
            .order_by(func.max(CANLogModel.created_at).desc())
        )
        result = await self._session.execute(stmt)
        sessions = []
        for row in result.fetchall():
            sessions.append({
                "session_id": row.session_id,
                "frame_count": row.frame_count,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "ended_at": row.ended_at.isoformat() if row.ended_at else None,
            })
        return sessions

    async def get_session_frames(
        self, session_id: str, limit: int = 10000
    ) -> List[CANLogModel]:
        """Get all frames for a session (for replay)."""
        stmt = (
            select(CANLogModel)
            .where(CANLogModel.session_id == session_id)
            .order_by(CANLogModel.timestamp_us.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_batch(self, frames: List[Dict[str, Any]]) -> int:
        """Batch insert CAN frames."""
        models = []
        for frame_data in frames:
            model = CANLogModel(
                vehicle_id=frame_data.get("vehicle_id"),
                session_id=frame_data["session_id"],
                can_id=frame_data["can_id"],
                data=frame_data.get("data", b""),
                dlc=frame_data.get("dlc", 8),
                direction=frame_data.get("direction", "RX"),
                timestamp_us=frame_data["timestamp_us"],
            )
            models.append(model)

        self._session.add_all(models)
        await self._session.flush()
        return len(models)

    async def delete_session(self, session_id: str) -> int:
        """Delete all frames in a session."""
        stmt = delete(CANLogModel).where(CANLogModel.session_id == session_id)
        result = await self._session.execute(stmt)
        return result.rowcount


# ============================================================================
# SCENARIO REPOSITORY
# ============================================================================


class ScenarioRepository(BaseRepository):
    """Data access for ScenarioModel and ScenarioRunModel."""

    model = ScenarioModel

    async def get_by_slug(self, slug: str) -> Optional[ScenarioModel]:
        """Get scenario by slug."""
        stmt = select(ScenarioModel).where(ScenarioModel.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_runs(
        self, scenario_id: Optional[int] = None, limit: int = 50
    ) -> List[ScenarioRunModel]:
        """Get scenario execution history."""
        stmt = select(ScenarioRunModel).order_by(
            ScenarioRunModel.started_at.desc()
        )
        if scenario_id:
            stmt = stmt.where(ScenarioRunModel.scenario_id == scenario_id)
        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create_run(self, data: Dict[str, Any]) -> ScenarioRunModel:
        """Record a scenario execution."""
        run = ScenarioRunModel(
            scenario_id=data["scenario_id"],
            vehicle_id=data.get("vehicle_id"),
            session_id=data.get("session_id", str(uuid.uuid4())),
            status="running",
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def complete_run(self, session_id: str, status: str = "completed") -> bool:
        """Mark a scenario run as complete."""
        stmt = (
            update(ScenarioRunModel)
            .where(ScenarioRunModel.session_id == session_id)
            .values(
                status=status,
                ended_at=datetime.now(timezone.utc),
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


# ============================================================================
# SYSTEM CONFIG REPOSITORY
# ============================================================================


class SystemConfigRepository(BaseRepository):
    """Data access for SystemConfigModel."""

    model = SystemConfigModel

    async def get(self, key: str) -> Optional[str]:
        """Get a config value by key."""
        config = await self._session.get(SystemConfigModel, key)
        return config.value if config else None

    async def set(self, key: str, value: str, description: str = "") -> None:
        """Set a config value (upsert)."""
        config = await self._session.get(SystemConfigModel, key)
        if config:
            config.value = value
            config.updated_at = datetime.now(timezone.utc)
        else:
            config = SystemConfigModel(
                key=key, value=value, description=description
            )
            self._session.add(config)
        await self._session.flush()

    async def get_all(self) -> Dict[str, str]:
        """Get all config as dictionary."""
        stmt = select(SystemConfigModel)
        result = await self._session.execute(stmt)
        configs = result.scalars().all()
        return {c.key: c.value for c in configs}

    async def delete(self, key: str) -> bool:
        """Delete a config entry."""
        config = await self._session.get(SystemConfigModel, key)
        if config:
            await self._session.delete(config)
            return True
        return False