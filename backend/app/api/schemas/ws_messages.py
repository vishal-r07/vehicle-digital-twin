"""
============================================================================
AutoTwin AI - WebSocket Message Schemas
============================================================================
Defines the WebSocket message protocol between backend and frontend.

All messages follow the envelope format:
  {
    "type": string,       // Message type identifier
    "seq": int,           // Sequence number (incrementing)
    "timestamp": float,   // Unix timestamp
    "payload": { ... }    // Type-specific data
  }

Server → Client Messages:
  - vehicle_state:    Real-time vehicle data (20 Hz)
  - fault_event:      New fault detected
  - fault_resolved:   Fault cleared
  - health_update:    Health score update
  - timeline_event:   Timeline entry added
  - scenario_update:  Scenario progress
  - connection_ack:   Initial handshake
  - heartbeat:        Keep-alive
  - error:            Error notification

Client → Server Messages:
  - subscribe:        Channel subscription
  - request_state:    Full state request
  - scenario_command: Start/stop scenario
  - acknowledge_fault: Mark fault as seen
============================================================================
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# ============================================================================
# MESSAGE ENVELOPE (Base)
# ============================================================================


class WSMessageEnvelope(BaseModel):
    """
    Base envelope for all WebSocket messages.

    Every message (both directions) uses this structure.
    """

    type: str = Field(..., description="Message type identifier")
    seq: int = Field(0, description="Sequence number")
    timestamp: float = Field(..., description="Unix timestamp")
    payload: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "vehicle_state",
                    "seq": 15423,
                    "timestamp": 1705312200.123,
                    "payload": {"speed": 58.0, "rpm": 2450},
                }
            ]
        }
    }


# ============================================================================
# SERVER → CLIENT: VEHICLE STATE
# ============================================================================


class WSVehicleStatePayload(BaseModel):
    """Vehicle state update payload (sent at 20 Hz)."""

    # Primary signals
    speed: float = Field(0.0, description="Vehicle speed (km/h)")
    rpm: int = Field(0, description="Engine RPM")
    fuel: float = Field(100.0, description="Fuel level (%)")
    temp: float = Field(25.0, description="Coolant temperature (°C)")
    battery: float = Field(12.6, description="Battery voltage (V)")
    steering: float = Field(0.0, description="Steering angle (deg)")
    brake: int = Field(0, description="Brake applied (0/1)")
    accelerator: float = Field(0.0, description="Accelerator position (%)")
    gear: str = Field("P", description="Gear position (P/R/N/D/S/L/M)")
    door: str = Field("Closed", description="Door status")
    indicator: int = Field(0, description="Indicator bitmask")
    headlight: int = Field(0, description="Headlight bitmask")
    engine_load: float = Field(0.0, description="Engine load (%)")
    ambient_temp: float = Field(25.0, description="Ambient temperature (°C)")
    odometer: float = Field(0.0, description="Odometer (km)")

    # Metadata
    frame_count: int = 0
    can_active: bool = False
    uptime: float = 0.0
    sequence: int = 0
    overall_health: float = 100.0
    active_faults: int = 0


class WSVehicleState(BaseModel):
    """Complete vehicle state WebSocket message."""

    type: str = "vehicle_state"
    seq: int = 0
    timestamp: float = 0.0
    payload: WSVehicleStatePayload


# ============================================================================
# SERVER → CLIENT: FAULT EVENT
# ============================================================================


class WSFaultEventPayload(BaseModel):
    """Fault detection event payload."""

    fault_id: str
    rule_id: str
    severity: str
    confidence: float
    priority: int
    subsystem: str
    message: str
    signal_values: Dict[str, float] = Field(default_factory=dict)
    possible_causes: List[str] = Field(default_factory=list)
    recommendation: str = ""
    estimated_repair_time: str = ""
    related_dtcs: List[str] = Field(default_factory=list)


class WSFaultEvent(BaseModel):
    """Fault detection WebSocket message."""

    type: str = "fault_event"
    seq: int = 0
    timestamp: float = 0.0
    payload: WSFaultEventPayload


# ============================================================================
# SERVER → CLIENT: FAULT RESOLVED
# ============================================================================


class WSFaultResolvedPayload(BaseModel):
    """Fault resolution event payload."""

    fault_id: str
    rule_id: str
    resolution: str = Field("auto", description="auto, manual, timeout")
    duration_s: float = 0.0


class WSFaultResolved(BaseModel):
    """Fault resolution WebSocket message."""

    type: str = "fault_resolved"
    seq: int = 0
    timestamp: float = 0.0
    payload: WSFaultResolvedPayload


# ============================================================================
# SERVER → CLIENT: HEALTH UPDATE
# ============================================================================


class WSHealthUpdatePayload(BaseModel):
    """Health score update payload."""

    overall: float
    engine: float = 100.0
    transmission: float = 100.0
    brakes: float = 100.0
    cooling: float = 100.0
    battery: float = 100.0
    electrical: float = 100.0
    fuel: float = 100.0
    status: str = "good"
    active_fault_count: int = 0
    trend: str = "stable"


class WSHealthUpdate(BaseModel):
    """Health update WebSocket message."""

    type: str = "health_update"
    seq: int = 0
    timestamp: float = 0.0
    payload: WSHealthUpdatePayload


# ============================================================================
# SERVER → CLIENT: TIMELINE EVENT
# ============================================================================


class WSTimelineEventPayload(BaseModel):
    """Timeline event payload."""

    entry_id: str
    event_type: str
    severity: str
    message: str
    signal_name: str = ""
    signal_value: float = 0.0
    subsystem: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WSTimelineEvent(BaseModel):
    """Timeline event WebSocket message."""

    type: str = "timeline_event"
    seq: int = 0
    timestamp: float = 0.0
    payload: WSTimelineEventPayload


# ============================================================================
# SERVER → CLIENT: SCENARIO UPDATE
# ============================================================================


class WSScenarioUpdatePayload(BaseModel):
    """Scenario progress update payload."""

    scenario_id: str
    scenario_name: str = ""
    status: str = Field("running", description="running, paused, completed, stopped")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="0.0 to 1.0")
    elapsed_s: float = 0.0
    total_duration_s: float = 0.0
    current_phase: str = ""
    injected_signals: List[str] = Field(default_factory=list)


class WSScenarioUpdate(BaseModel):
    """Scenario update WebSocket message."""

    type: str = "scenario_update"
    seq: int = 0
    timestamp: float = 0.0
    payload: WSScenarioUpdatePayload


# ============================================================================
# SERVER → CLIENT: CONNECTION ACK
# ============================================================================


class WSConnectionAckPayload(BaseModel):
    """Connection acknowledgment payload."""

    client_id: str
    server_version: str = "1.0.0"
    active_vehicle: Optional[str] = None
    update_rate_hz: int = 20
    features: List[str] = Field(
        default=["diagnostics", "scenarios", "replay", "health"],
    )
    session_id: str = ""


class WSConnectionAck(BaseModel):
    """Connection acknowledgment WebSocket message."""

    type: str = "connection_ack"
    seq: int = 1
    timestamp: float = 0.0
    payload: WSConnectionAckPayload


# ============================================================================
# SERVER → CLIENT: HEARTBEAT
# ============================================================================


class WSHeartbeatPayload(BaseModel):
    """Heartbeat / keep-alive payload."""

    uptime_s: float = 0.0
    active_connections: int = 0
    frames_processed: int = 0
    faults_active: int = 0
    memory_mb: float = 0.0


class WSHeartbeat(BaseModel):
    """Heartbeat WebSocket message."""

    type: str = "heartbeat"
    seq: int = 0
    timestamp: float = 0.0
    payload: WSHeartbeatPayload


# ============================================================================
# SERVER → CLIENT: ERROR
# ============================================================================


class WSErrorPayload(BaseModel):
    """Error notification payload."""

    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = True


class WSError(BaseModel):
    """Error WebSocket message."""

    type: str = "error"
    seq: int = 0
    timestamp: float = 0.0
    payload: WSErrorPayload


# ============================================================================
# CLIENT → SERVER: SUBSCRIBE
# ============================================================================


class WSSubscribePayload(BaseModel):
    """Channel subscription request."""

    channels: List[str] = Field(
        default=[
            "vehicle_state",
            "fault_event",
            "fault_resolved",
            "health_update",
            "timeline_event",
            "scenario_update",
        ],
        description="Channels to subscribe to",
    )


class WSSubscribe(BaseModel):
    """Client subscription message."""

    type: str = "subscribe"
    payload: WSSubscribePayload


# ============================================================================
# CLIENT → SERVER: REQUEST STATE
# ============================================================================


class WSRequestStatePayload(BaseModel):
    """Full state request."""

    full: bool = Field(True, description="Request full state vs compact")


class WSRequestState(BaseModel):
    """Client state request message."""

    type: str = "request_state"
    payload: WSRequestStatePayload


# ============================================================================
# CLIENT → SERVER: SCENARIO COMMAND
# ============================================================================


class WSScenarioCommandPayload(BaseModel):
    """Scenario control command."""

    action: str = Field(..., description="start, stop, pause, resume")
    scenario_id: Optional[str] = None
    speed: float = 1.0


class WSScenarioCommand(BaseModel):
    """Client scenario command message."""

    type: str = "scenario_command"
    payload: WSScenarioCommandPayload


# ============================================================================
# CLIENT → SERVER: ACKNOWLEDGE FAULT
# ============================================================================


class WSAcknowledgeFaultPayload(BaseModel):
    """Fault acknowledgment command."""

    fault_id: str
    notes: str = ""


class WSAcknowledgeFault(BaseModel):
    """Client fault acknowledgment message."""

    type: str = "acknowledge_fault"
    payload: WSAcknowledgeFaultPayload


# ============================================================================
# CLIENT → SERVER: GENERIC COMMAND
# ============================================================================


class WSClientCommand(BaseModel):
    """
    Generic client command (union type for parsing).

    Use this to parse any incoming client message:
        cmd = WSClientCommand.model_validate_json(raw_data)
    """

    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def parse(cls, raw: str) -> "WSClientCommand":
        """Parse raw JSON string into a client command."""
        import json
        data = json.loads(raw)
        return cls(**data)


# ============================================================================
# MESSAGE TYPE REGISTRY (for serialization)
# ============================================================================

# Server → Client message types
SERVER_MESSAGE_TYPES = {
    "vehicle_state": WSVehicleState,
    "fault_event": WSFaultEvent,
    "fault_resolved": WSFaultResolved,
    "health_update": WSHealthUpdate,
    "timeline_event": WSTimelineEvent,
    "scenario_update": WSScenarioUpdate,
    "connection_ack": WSConnectionAck,
    "heartbeat": WSHeartbeat,
    "error": WSError,
}

# Client → Server message types
CLIENT_MESSAGE_TYPES = {
    "subscribe": WSSubscribe,
    "request_state": WSRequestState,
    "scenario_command": WSScenarioCommand,
    "acknowledge_fault": WSAcknowledgeFault,
}


def create_ws_message(msg_type: str, payload: Dict[str, Any], seq: int = 0) -> Dict[str, Any]:
    """
    Create a WebSocket message dictionary.

    Args:
        msg_type: Message type identifier
        payload: Message payload
        seq: Sequence number

    Returns:
        Complete message dictionary ready for JSON serialization.
    """
    import time
    return {
        "type": msg_type,
        "seq": seq,
        "timestamp": time.time(),
        "payload": payload,
    }