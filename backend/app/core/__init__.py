"""
============================================================================
AutoTwin AI - Core Module
============================================================================
Foundation layer providing:
  - EventBus: Internal async pub/sub for decoupled communication
  - VehicleStateManager: Central vehicle state (single source of truth)
  - Exceptions: Typed exception hierarchy
  - Constants: Enums, thresholds, configuration values

All other modules depend on this layer. This layer depends on nothing
except Python standard library and pydantic.

Usage:
    from app.core import EventBus, VehicleStateManager, Severity, EventType
============================================================================
"""

from app.core.event_bus import EventBus, Event, EventSubscription  # noqa: F401
from app.core.state_manager import VehicleStateManager, SignalValue  # noqa: F401
from app.core.exceptions import (  # noqa: F401
    AutoTwinError,
    SerialConnectionError,
    CANConnectionError,
    CANBusOffError,
    VehicleNotFoundError,
    VehiclePluginError,
    InvalidSignalError,
    DBCParseError,
    FaultRuleError,
    FaultNotFoundError,
    ScenarioNotFoundError,
    ScenarioAlreadyActiveError,
    ReplayLogNotFoundError,
    ReplayError,
    WebSocketError,
    DatabaseError,
)
from app.core.constants import (  # noqa: F401
    Severity,
    Subsystem,
    EventType,
    WSMessageType,
    GearPosition,
    DataSource,
    SystemStatus,
    CANId,
    DefaultThresholds,
    HEALTH_WEIGHTS,
)

__all__ = [
    "EventBus",
    "Event",
    "EventSubscription",
    "VehicleStateManager",
    "SignalValue",
    "AutoTwinError",
    "Severity",
    "Subsystem",
    "EventType",
    "WSMessageType",
    "GearPosition",
    "DataSource",
    "SystemStatus",
    "CANId",
    "DefaultThresholds",
    "HEALTH_WEIGHTS",
]