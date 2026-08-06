"""
============================================================================
AutoTwin AI - Vehicle State Module
============================================================================
Manages the digital representation of the vehicle:
  - VehicleState: Complete vehicle state dataclass
  - StateUpdater: Applies CAN signals to state
  - HealthCalculator: Computes subsystem and overall health scores
  - Subsystems: Individual subsystem models (Engine, Brakes, etc.)

This module sits between the CAN Parser and the Diagnostics Engine.
It transforms raw decoded signals into a structured, queryable
vehicle state that drives the dashboard, 3D twin, and diagnostics.

Data Flow:
  CANFrameParser → StateUpdater → VehicleState → HealthCalculator
                                        ↓
                                  WebSocket Broadcast
                                  3D Digital Twin
                                  Diagnostic Engine
============================================================================
"""

from app.vehicle.vehicle_state import (  # noqa: F401
    VehicleState,
    EngineState,
    TransmissionState,
    BrakeState,
    CoolingState,
    BatteryState,
    BodyState,
    SteeringState,
    FuelState,
    ElectricalState,
)
from app.vehicle.state_updater import StateUpdater  # noqa: F401
from app.vehicle.health_calculator import (  # noqa: F401
    HealthCalculator,
    HealthScore,
    SubsystemHealth,
)
from app.vehicle.subsystems import (  # noqa: F401
    SubsystemBase,
    EngineSubsystem,
    BrakeSubsystem,
    CoolingSubsystem,
    BatterySubsystem,
    TransmissionSubsystem,
    ElectricalSubsystem,
    get_subsystem_registry,
)

__all__ = [
    "VehicleState",
    "EngineState",
    "TransmissionState",
    "BrakeState",
    "CoolingState",
    "BatteryState",
    "BodyState",
    "SteeringState",
    "FuelState",
    "ElectricalState",
    "StateUpdater",
    "HealthCalculator",
    "HealthScore",
    "SubsystemHealth",
    "SubsystemBase",
    "EngineSubsystem",
    "BrakeSubsystem",
    "CoolingSubsystem",
    "BatterySubsystem",
    "TransmissionSubsystem",
    "ElectricalSubsystem",
    "get_subsystem_registry",
]