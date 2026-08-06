"""
============================================================================
AutoTwin AI - SQLAlchemy ORM Models
============================================================================
Database models matching the Alembic migration schema (001_initial_schema).

Models:
  - Vehicle:           Vehicle registry entries
  - VehicleProfile:    Per-vehicle configuration (DBC path, rules, 3D model)
  - FaultEventModel:   Detected fault events
  - TimelineEventModel: Chronological event log
  - HealthSnapshotModel: Periodic health score snapshots
  - CANLogModel:       Raw CAN frame recordings (for replay)
  - ScenarioModel:     Scenario definitions
  - ScenarioRunModel:  Scenario execution history
  - SystemConfigModel: Key-value system configuration

Relationships:
  Vehicle 1──1 VehicleProfile
  Vehicle 1──* FaultEventModel
  Vehicle 1──* TimelineEventModel
  Vehicle 1──* HealthSnapshotModel
  Vehicle 1──* CANLogModel
  Scenario 1──* ScenarioRunModel
============================================================================
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    BigInteger,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


# ============================================================================
# HELPER: UTC TIMESTAMP
# ============================================================================


def utcnow() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


# ============================================================================
# VEHICLE MODELS
# ============================================================================


class Vehicle(Base):
    """
    Vehicle registry entry.

    Represents a vehicle that can be selected as the active digital twin.
    Each vehicle has associated DBC, fault rules, and 3D model via profile.
    """

    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    make = Column(String(64), nullable=False)
    model = Column(String(64), nullable=False)
    year = Column(Integer, nullable=True)
    category = Column(String(32), nullable=True)  # sedan, SUV, EV, truck
    engine_type = Column(String(64), nullable=True)
    transmission_type = Column(String(32), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    profile = relationship("VehicleProfile", back_populates="vehicle", uselist=False)
    fault_events = relationship("FaultEventModel", back_populates="vehicle")
    timeline_events = relationship("TimelineEventModel", back_populates="vehicle")
    health_snapshots = relationship("HealthSnapshotModel", back_populates="vehicle")
    can_logs = relationship("CANLogModel", back_populates="vehicle")

    def __repr__(self) -> str:
        return f"<Vehicle(id={self.id}, slug='{self.slug}', name='{self.name}')>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "category": self.category,
            "engine_type": self.engine_type,
            "transmission_type": self.transmission_type,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class VehicleProfile(Base):
    """
    Vehicle-specific configuration and file paths.

    Links a vehicle to its DBC file, fault rules, 3D model,
    and dashboard layout.
    """

    __tablename__ = "vehicle_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
    )
    dbc_path = Column(String(256), nullable=True)
    fault_rules_path = Column(String(256), nullable=True)
    model_3d_path = Column(String(256), nullable=True)
    dashboard_layout = Column(Text, nullable=True)  # JSON string
    subsystem_map = Column(Text, nullable=True)     # JSON string
    signal_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="profile")

    def __repr__(self) -> str:
        return f"<VehicleProfile(vehicle_id={self.vehicle_id})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "dbc_path": self.dbc_path,
            "fault_rules_path": self.fault_rules_path,
            "model_3d_path": self.model_3d_path,
            "signal_count": self.signal_count,
        }


# ============================================================================
# DIAGNOSTIC MODELS
# ============================================================================


class FaultEventModel(Base):
    """
    Detected fault event.

    Stored when a fault rule triggers. Retained for history and analysis.
    """

    __tablename__ = "fault_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fault_id = Column(String(64), unique=True, nullable=False, index=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    rule_id = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    message = Column(String(512), nullable=False)
    signal_values = Column(Text, nullable=True)       # JSON
    possible_causes = Column(Text, nullable=True)     # JSON array
    recommendation = Column(String(512), nullable=True)
    estimated_repair_time = Column(String(64), nullable=True)
    priority = Column(Integer, nullable=True)
    subsystem = Column(String(32), nullable=True)
    acknowledged = Column(Boolean, default=False, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="fault_events")

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_fault_events_vehicle_severity", "vehicle_id", "severity"),
        Index("ix_fault_events_resolved_created", "resolved", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<FaultEvent(id={self.fault_id}, rule='{self.rule_id}', severity='{self.severity}')>"

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "fault_id": self.fault_id,
            "vehicle_id": self.vehicle_id,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "confidence": self.confidence,
            "message": self.message,
            "signal_values": json.loads(self.signal_values) if self.signal_values else {},
            "possible_causes": json.loads(self.possible_causes) if self.possible_causes else [],
            "recommendation": self.recommendation,
            "estimated_repair_time": self.estimated_repair_time,
            "priority": self.priority,
            "subsystem": self.subsystem,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TimelineEventModel(Base):
    """
    Chronological event log entry.

    Records all significant events for audit trail and analysis.
    """

    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type = Column(String(32), nullable=False, index=True)
    severity = Column(String(16), nullable=True)
    message = Column(String(512), nullable=False)
    signal_name = Column(String(64), nullable=True)
    signal_value = Column(Float, nullable=True)
    metadata = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="timeline_events")

    __table_args__ = (
        Index("ix_timeline_vehicle_created", "vehicle_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TimelineEvent(id={self.id}, type='{self.event_type}')>"

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "signal_name": self.signal_name,
            "signal_value": self.signal_value,
            "metadata": json.loads(self.metadata) if self.metadata else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class HealthSnapshotModel(Base):
    """
    Periodic health score snapshot.

    Stored every N seconds for trend analysis and reporting.
    """

    __tablename__ = "health_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
    )
    overall_score = Column(Float, nullable=False)
    engine_score = Column(Float, nullable=True)
    battery_score = Column(Float, nullable=True)
    brake_score = Column(Float, nullable=True)
    cooling_score = Column(Float, nullable=True)
    transmission_score = Column(Float, nullable=True)
    electrical_score = Column(Float, nullable=True)
    active_fault_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="health_snapshots")

    __table_args__ = (
        Index("ix_health_vehicle_created", "vehicle_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<HealthSnapshot(vehicle={self.vehicle_id}, overall={self.overall_score})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "overall_score": self.overall_score,
            "engine_score": self.engine_score,
            "battery_score": self.battery_score,
            "brake_score": self.brake_score,
            "cooling_score": self.cooling_score,
            "transmission_score": self.transmission_score,
            "electrical_score": self.electrical_score,
            "active_fault_count": self.active_fault_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# CAN LOG MODEL
# ============================================================================


class CANLogModel(Base):
    """
    Raw CAN frame recording for replay.

    Stores individual CAN frames with timestamps for
    accurate replay and post-event analysis.
    """

    __tablename__ = "can_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id = Column(String(64), nullable=False, index=True)
    can_id = Column(Integer, nullable=False)
    data = Column(LargeBinary, nullable=True)
    dlc = Column(Integer, nullable=True)
    direction = Column(String(2), nullable=True)  # RX or TX
    timestamp_us = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="can_logs")

    __table_args__ = (
        Index("ix_can_logs_session_timestamp", "session_id", "timestamp_us"),
    )

    def __repr__(self) -> str:
        return f"<CANLog(session='{self.session_id}', id=0x{self.can_id:03X})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "session_id": self.session_id,
            "can_id": self.can_id,
            "data": self.data.hex() if self.data else "",
            "dlc": self.dlc,
            "direction": self.direction,
            "timestamp_us": self.timestamp_us,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================================
# SCENARIO MODELS
# ============================================================================


class ScenarioModel(Base):
    """Scenario definition stored in database."""

    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(String(512), nullable=True)
    category = Column(String(32), nullable=True)  # normal, fault, stress
    definition = Column(Text, nullable=True)      # JSON
    duration_s = Column(Integer, nullable=True)
    is_builtin = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    # Relationships
    runs = relationship("ScenarioRunModel", back_populates="scenario")

    def __repr__(self) -> str:
        return f"<Scenario(slug='{self.slug}', name='{self.name}')>"

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "definition": json.loads(self.definition) if self.definition else None,
            "duration_s": self.duration_s,
            "is_builtin": self.is_builtin,
        }


class ScenarioRunModel(Base):
    """Scenario execution record."""

    __tablename__ = "scenario_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(
        Integer,
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id = Column(String(64), unique=True, nullable=False)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(16), default="running", nullable=False)
    fault_count = Column(Integer, default=0)
    notes = Column(Text, nullable=True)

    # Relationships
    scenario = relationship("ScenarioModel", back_populates="runs")

    def __repr__(self) -> str:
        return f"<ScenarioRun(session='{self.session_id}', status='{self.status}')>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "vehicle_id": self.vehicle_id,
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "status": self.status,
            "fault_count": self.fault_count,
        }


# ============================================================================
# SYSTEM CONFIGURATION
# ============================================================================


class SystemConfigModel(Base):
    """Key-value system configuration stored in database."""

    __tablename__ = "system_config"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)
    description = Column(String(256), nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    def __repr__(self) -> str:
        return f"<SystemConfig(key='{self.key}')>"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "description": self.description,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }