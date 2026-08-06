"""
============================================================================
AutoTwin AI - Application Constants & Enumerations
============================================================================
All enums, magic numbers, and shared constants.
No business logic — pure data definitions.
============================================================================
"""

from enum import Enum, IntEnum
from typing import Dict


# ============================================================================
# SEVERITY LEVELS
# ============================================================================


class Severity(str, Enum):
    """Fault/diagnostic severity levels (ordered by criticality)."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def weight(self) -> int:
        """Numeric weight for sorting (higher = more severe)."""
        return {
            Severity.INFO: 1,
            Severity.LOW: 2,
            Severity.MEDIUM: 3,
            Severity.HIGH: 4,
            Severity.CRITICAL: 5,
        }[self]

    @property
    def color(self) -> str:
        """UI color for this severity level."""
        return {
            Severity.INFO: "#64748b",
            Severity.LOW: "#22c55e",
            Severity.MEDIUM: "#eab308",
            Severity.HIGH: "#f97316",
            Severity.CRITICAL: "#ef4444",
        }[self]

    @classmethod
    def from_string(cls, value: str) -> "Severity":
        """Parse severity from string (case-insensitive)."""
        try:
            return cls(value.upper())
        except ValueError:
            return cls.INFO


# ============================================================================
# VEHICLE SUBSYSTEMS
# ============================================================================


class Subsystem(str, Enum):
    """Vehicle subsystem identifiers for diagnostics and 3D highlighting."""

    ENGINE = "engine"
    TRANSMISSION = "transmission"
    BRAKES = "brakes"
    COOLING = "cooling"
    BATTERY = "battery"
    BODY = "body"
    STEERING = "steering"
    ELECTRICAL = "electrical"
    FUEL = "fuel"
    SUSPENSION = "suspension"
    WHEELS = "wheels"
    EXHAUST = "exhaust"

    @property
    def display_name(self) -> str:
        """Human-readable name."""
        return self.value.capitalize()


# ============================================================================
# EVENT TYPES (Internal Event Bus)
# ============================================================================


class EventType(str, Enum):
    """Event types for the internal pub/sub system."""

    # State events
    STATE_CHANGED = "state_changed"
    STATE_UPDATED = "state_updated"
    STATE_RESET = "state_reset"
    SIGNAL_STALE = "signal_stale"

    # CAN events
    CAN_FRAME_RECEIVED = "can_frame_received"
    CAN_FRAME_DECODED = "can_frame_decoded"
    CAN_TIMEOUT = "can_timeout"
    CAN_BUS_OFF = "can_bus_off"
    CAN_ERROR = "can_error"

    # Connection events
    SERIAL_CONNECTED = "serial_connected"
    SERIAL_DISCONNECTED = "serial_disconnected"
    SERIAL_ERROR = "serial_error"

    # Diagnostic events
    FAULT_DETECTED = "fault_detected"
    FAULT_RESOLVED = "fault_resolved"
    FAULT_ACKNOWLEDGED = "fault_acknowledged"
    HEALTH_UPDATED = "health_updated"
    THRESHOLD_WARNING = "threshold_warning"

    # Timeline events
    TIMELINE_EVENT = "timeline_event"

    # Scenario events
    SCENARIO_STARTED = "scenario_started"
    SCENARIO_TICK = "scenario_tick"
    SCENARIO_STOPPED = "scenario_stopped"
    SCENARIO_COMPLETED = "scenario_completed"

    # Replay events
    REPLAY_STARTED = "replay_started"
    REPLAY_PAUSED = "replay_paused"
    REPLAY_SEEKED = "replay_seeked"
    REPLAY_STOPPED = "replay_stopped"

    # System events
    VEHICLE_SELECTED = "vehicle_selected"
    SYSTEM_ERROR = "system_error"
    SHUTDOWN_REQUESTED = "shutdown_requested"


# ============================================================================
# WEBSOCKET MESSAGE TYPES
# ============================================================================


class WSMessageType(str, Enum):
    """WebSocket message type identifiers (protocol definition)."""

    # Server → Client
    VEHICLE_STATE = "vehicle_state"
    FAULT_EVENT = "fault_event"
    FAULT_RESOLVED = "fault_resolved"
    HEALTH_UPDATE = "health_update"
    TIMELINE_EVENT = "timeline_event"
    SCENARIO_UPDATE = "scenario_update"
    REPLAY_UPDATE = "replay_update"
    CONNECTION_ACK = "connection_ack"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

    # Client → Server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    REQUEST_STATE = "request_state"
    SCENARIO_COMMAND = "scenario_command"
    REPLAY_COMMAND = "replay_command"
    ACKNOWLEDGE_FAULT = "acknowledge_fault"


# ============================================================================
# GEAR POSITIONS
# ============================================================================


class GearPosition(str, Enum):
    """Transmission gear positions."""

    PARK = "P"
    REVERSE = "R"
    NEUTRAL = "N"
    DRIVE = "D"
    SPORT = "S"
    LOW = "L"
    MANUAL = "M"
    UNKNOWN = "?"

    @classmethod
    def from_int(cls, value: int) -> "GearPosition":
        """Convert integer (from CAN) to GearPosition."""
        mapping = {0: cls.PARK, 1: cls.REVERSE, 2: cls.NEUTRAL,
                   3: cls.DRIVE, 4: cls.SPORT, 5: cls.LOW, 6: cls.MANUAL}
        return mapping.get(value, cls.UNKNOWN)


# ============================================================================
# DATA SOURCE TYPES
# ============================================================================


class DataSource(str, Enum):
    """Origin of vehicle data."""

    LIVE_SERIAL = "live_serial"
    LIVE_USB_CAN = "live_usb_can"
    LIVE_OBD2 = "live_obd2"
    SIMULATION = "simulation"
    REPLAY = "replay"
    SCENARIO = "scenario"


# ============================================================================
# SYSTEM STATUS
# ============================================================================


class SystemStatus(str, Enum):
    """Overall system operational status."""

    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    DEGRADED = "degraded"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"


# ============================================================================
# CAN MESSAGE IDs (Phase 1)
# ============================================================================


class CANId(IntEnum):
    """Phase 1 CAN arbitration IDs."""

    SPEED = 0x100
    RPM = 0x101
    FUEL = 0x102
    TEMP = 0x103
    BATTERY = 0x104
    STEERING = 0x105
    BRAKE = 0x106
    ACCELERATOR = 0x107
    GEAR = 0x108
    DOOR = 0x109
    INDICATORS = 0x10A
    HEADLIGHTS = 0x10B
    WHEEL_SPEED = 0x10C
    ENGINE_LOAD = 0x10D
    AMBIENT_TEMP = 0x10E
    ODOMETER = 0x10F


# ============================================================================
# SIGNAL NAMES (Canonical)
# ============================================================================


class SignalName(str, Enum):
    """Canonical signal names matching serial protocol keys."""

    SPEED = "speed"
    RPM = "rpm"
    FUEL = "fuel"
    TEMP = "temp"
    BATTERY = "battery"
    STEERING = "steering"
    BRAKE = "brake"
    ACCEL = "accelerator"
    GEAR = "gear"
    DOOR = "door"
    INDICATOR = "indicator"
    HEADLIGHT = "headlight"
    ENGINE_LOAD = "engine_load"
    AMBIENT_TEMP = "ambient_temp"
    ODOMETER = "odometer"
    WHEEL_FL = "wheel_fl"
    WHEEL_FR = "wheel_fr"
    WHEEL_RL = "wheel_rl"
    WHEEL_RR = "wheel_rr"
    ABS = "abs"
    BRAKE_PRESSURE = "brake_pressure"


# ============================================================================
# DEFAULT DIAGNOSTIC THRESHOLDS
# ============================================================================


class DefaultThresholds:
    """
    Default diagnostic thresholds.
    Can be overridden per-vehicle via fault_rules.yaml.
    """

    # Engine Temperature (°C)
    TEMP_WARNING: float = 100.0
    TEMP_HIGH: float = 105.0
    TEMP_CRITICAL: float = 120.0
    TEMP_MIN_VALID: float = -40.0
    TEMP_MAX_VALID: float = 215.0

    # Engine RPM
    RPM_IDLE_MIN: int = 600
    RPM_IDLE_MAX: int = 1000
    RPM_WARNING: int = 5500
    RPM_REDLINE: int = 6500
    RPM_MAX: int = 8000

    # Battery Voltage (V)
    BATTERY_LOW: float = 11.5
    BATTERY_CRITICAL: float = 10.5
    BATTERY_OVERCHARGE: float = 15.0
    BATTERY_NORMAL_MIN: float = 12.0
    BATTERY_NORMAL_MAX: float = 14.8

    # Fuel Level (%)
    FUEL_LOW: float = 15.0
    FUEL_CRITICAL: float = 5.0
    FUEL_EMPTY: float = 0.0

    # Vehicle Speed (km/h)
    SPEED_HIGH: float = 200.0
    SPEED_MAX: float = 300.0

    # Steering Angle (degrees)
    STEERING_MAX: float = 720.0

    # Engine Load (%)
    LOAD_HIGH: float = 90.0

    # Brake
    BRAKE_PRESSURE_MAX: float = 200.0

    # Timing
    CAN_TIMEOUT_MS: int = 2000
    SIGNAL_STALE_MULTIPLIER: float = 2.5  # Stale if no update for 2.5× expected period


# ============================================================================
# HEALTH SCORE CONFIGURATION
# ============================================================================


HEALTH_WEIGHTS: Dict[str, float] = {
    Subsystem.ENGINE.value: 0.25,
    Subsystem.TRANSMISSION.value: 0.15,
    Subsystem.BRAKES.value: 0.20,
    Subsystem.COOLING.value: 0.15,
    Subsystem.BATTERY.value: 0.10,
    Subsystem.ELECTRICAL.value: 0.10,
    Subsystem.FUEL.value: 0.05,
}

HEALTH_SCORE_MIN: float = 0.0
HEALTH_SCORE_MAX: float = 100.0
HEALTH_SCORE_CRITICAL: float = 30.0
HEALTH_SCORE_WARNING: float = 60.0


# ============================================================================
# TIMING CONSTANTS
# ============================================================================


class Timing:
    """Application timing constants (milliseconds unless noted)."""

    BROADCAST_INTERVAL_MS: int = 50          # 20 Hz state broadcast
    HEALTH_UPDATE_INTERVAL_S: int = 10       # Health recalculation
    HEARTBEAT_INTERVAL_S: int = 5            # WebSocket heartbeat
    CAN_CHECK_INTERVAL_MS: int = 1           # CAN polling interval
    SERIAL_RECONNECT_DELAY_MS: int = 2000    # Serial reconnection delay
    FAULT_COOLDOWN_S: int = 30               # Fault re-trigger cooldown
    TIMELINE_CLEANUP_INTERVAL_S: int = 300   # Timeline cleanup every 5 min
    STALE_CHECK_INTERVAL_MS: int = 500       # Signal staleness check


# ============================================================================
# BUFFER SIZES
# ============================================================================


class BufferSize:
    """Buffer and queue size limits."""

    CAN_FRAME_BUFFER: int = 1000       # Ring buffer for CAN frames
    STATE_HISTORY: int = 1000          # State snapshots (50s at 20Hz)
    TIMELINE_MAX: int = 10000          # Maximum timeline events
    FAULT_HISTORY_MAX: int = 500       # Maximum stored fault events
    WS_MESSAGE_QUEUE: int = 100        # Per-client WS message queue
    EVENT_HISTORY: int = 500           # Event bus history for debugging


# ============================================================================
# PROTOCOL CONSTANTS
# ============================================================================


SERIAL_FRAME_START: str = "---AUTOTWIN---"
SERIAL_FRAME_END: str = "---END---"
SERIAL_BAUD_RATE: int = 115200
CAN_BAUD_RATE: int = 500000
WS_DEFAULT_PORT: int = 8000
API_PREFIX: str = "/api"