"""
============================================================================
AutoTwin AI - API Schemas Package
============================================================================
Pydantic models for request/response validation and serialization.

Modules:
  - vehicle_schemas: Vehicle listing, selection, and profile schemas
  - diagnostic_schemas: Fault, health, and timeline schemas
  - ws_messages: WebSocket message format definitions

All schemas follow the response envelope pattern:
  {
    "success": true/false,
    "data": { ... },
    "error": { "code": "...", "message": "...", "details": {} },
    "meta": { "timestamp": "...", "request_id": "...", "duration_ms": 0 }
  }
============================================================================
"""

from app.api.schemas.vehicle_schemas import (  # noqa: F401
    VehicleSummarySchema,
    VehicleDetailSchema,
    VehicleSelectRequest,
    VehicleSelectResponse,
    VehicleListResponse,
    VehicleSignalsResponse,
    SubsystemInfoSchema,
)

from app.api.schemas.diagnostic_schemas import (  # noqa: F401
    FaultEventSchema,
    FaultListResponse,
    FaultDetailResponse,
    HealthScoreSchema,
    HealthResponse,
    TimelineEntrySchema,
    TimelineResponse,
    FaultRuleSchema,
    RecommendationSchema,
)

from app.api.schemas.ws_messages import (  # noqa: F401
    WSMessageEnvelope,
    WSVehicleState,
    WSFaultEvent,
    WSHealthUpdate,
    WSTimelineEvent,
    WSScenarioUpdate,
    WSConnectionAck,
    WSHeartbeat,
    WSError,
    WSClientCommand,
)

__all__ = [
    # Vehicle
    "VehicleSummarySchema",
    "VehicleDetailSchema",
    "VehicleSelectRequest",
    "VehicleSelectResponse",
    "VehicleListResponse",
    "VehicleSignalsResponse",
    "SubsystemInfoSchema",
    # Diagnostics
    "FaultEventSchema",
    "FaultListResponse",
    "FaultDetailResponse",
    "HealthScoreSchema",
    "HealthResponse",
    "TimelineEntrySchema",
    "TimelineResponse",
    "FaultRuleSchema",
    "RecommendationSchema",
    # WebSocket
    "WSMessageEnvelope",
    "WSVehicleState",
    "WSFaultEvent",
    "WSHealthUpdate",
    "WSTimelineEvent",
    "WSScenarioUpdate",
    "WSConnectionAck",
    "WSHeartbeat",
    "WSError",
    "WSClientCommand",
]