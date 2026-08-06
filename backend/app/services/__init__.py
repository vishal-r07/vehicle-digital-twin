"""
============================================================================
AutoTwin AI - Services Layer
============================================================================
Business logic orchestration between API endpoints and core modules.

Services:
  - VehicleService:      Vehicle plugin loading and selection
  - DiagnosticService:   Fault detection pipeline orchestration
  - ScenarioService:     Scenario and replay coordination
  - BroadcastService:    Real-time WebSocket broadcast loop

Architecture Position:
  API Endpoints → Services → Core Modules (State, Faults, Health)
  Services coordinate multiple core modules into cohesive operations.
============================================================================
"""

from app.services.vehicle_service import VehicleService  # noqa: F401
from app.services.diagnostic_service import DiagnosticService  # noqa: F401
from app.services.scenario_service import ScenarioService  # noqa: F401
from app.services.broadcast_service import BroadcastService  # noqa: F401

__all__ = [
    "VehicleService",
    "DiagnosticService",
    "ScenarioService",
    "BroadcastService",
]