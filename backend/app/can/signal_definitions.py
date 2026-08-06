"""
============================================================================
AutoTwin AI - Signal Definitions & Metadata
============================================================================
Defines signal configurations for Phase 1 CAN messages.
These serve as defaults when no DBC file is loaded, and provide
the canonical signal-to-subsystem mapping.

Each signal definition includes:
  - Name, CAN ID, bit position
  - Conversion factor/offset
  - Valid range
  - Expected update frequency
  - Subsystem mapping (for 3D highlighting)
  - Display format

Usage:
    config = get_signal_config("speed")
    physical = config.raw_to_physical(raw_value)
============================================================================
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional

from app.core.constants import Subsystem, CANId


# ============================================================================
# SIGNAL CONFIGURATION DATA STRUCTURE
# ============================================================================


@dataclass
class SignalConfig:
    """
    Configuration for a single CAN signal.

    Contains all metadata needed for decoding, validation,
    display, and diagnostic mapping.
    """

    # Identity
    name: str                         # Canonical signal name
    can_id: int                       # CAN message ID containing this signal
    display_name: str = ""            # Human-readable name for UI

    # Bit-level definition
    start_bit: int = 0                # Start bit in payload
    bit_length: int = 8               # Number of bits
    byte_order: str = "little_endian" # "little_endian" or "big_endian"
    is_signed: bool = False           # Two's complement if True

    # Conversion
    factor: float = 1.0               # physical = raw * factor + offset
    offset: float = 0.0

    # Validation
    min_value: float = 0.0            # Minimum valid physical value
    max_value: float = 1000.0         # Maximum valid physical value
    unit: str = ""                    # Engineering unit

    # Timing
    expected_frequency_hz: float = 20.0  # Expected update rate
    timeout_multiplier: float = 2.5      # Stale if no update for this × period

    # Mapping
    subsystem: str = Subsystem.BODY.value  # For 3D highlighting
    dashboard_gauge: str = ""              # Which gauge displays this

    # Default value
    default_value: float = 0.0

    def raw_to_physical(self, raw_value: int) -> float:
        """Convert raw integer to physical value."""
        return raw_value * self.factor + self.offset

    def physical_to_raw(self, physical_value: float) -> int:
        """Convert physical value to raw integer."""
        if self.factor == 0:
            return 0
        return int((physical_value - self.offset) / self.factor)

    def validate(self, physical_value: float) -> bool:
        """Check if value is within valid range."""
        return self.min_value <= physical_value <= self.max_value

    def clamp(self, physical_value: float) -> float:
        """Clamp value to valid range."""
        return max(self.min_value, min(self.max_value, physical_value))

    @property
    def timeout_ms(self) -> float:
        """Timeout in milliseconds before signal is considered stale."""
        if self.expected_frequency_hz <= 0:
            return 0
        period_ms = 1000.0 / self.expected_frequency_hz
        return period_ms * self.timeout_multiplier


@dataclass
class SignalDefinition:
    """
    Extended signal definition with diagnostic context.
    Used by the fault engine for threshold evaluation.
    """

    config: SignalConfig
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    warning_direction: str = "above"  # "above" or "below"
    diagnostic_message: str = ""
    related_dtcs: List[str] = field(default_factory=list)


# ============================================================================
# PHASE 1 SIGNAL DEFINITIONS
# ============================================================================


class Phase1Signals:
    """
    Complete signal definitions for Phase 1 (CAN IDs 0x100-0x10F).

    These match the STM32 firmware serial protocol output and the
    vehicle DBC file definitions.
    """

    # --- 0x100: Vehicle Speed ---
    SPEED = SignalConfig(
        name="speed",
        can_id=CANId.SPEED,
        display_name="Vehicle Speed",
        start_bit=0,
        bit_length=16,
        byte_order="little_endian",
        is_signed=False,
        factor=0.01,
        offset=0.0,
        min_value=0.0,
        max_value=300.0,
        unit="km/h",
        expected_frequency_hz=20.0,
        subsystem=Subsystem.BODY.value,
        dashboard_gauge="speedometer",
        default_value=0.0,
    )

    # --- 0x101: Engine RPM ---
    RPM = SignalConfig(
        name="rpm",
        can_id=CANId.RPM,
        display_name="Engine RPM",
        start_bit=0,
        bit_length=16,
        byte_order="little_endian",
        is_signed=False,
        factor=1.0,
        offset=0.0,
        min_value=0.0,
        max_value=8000.0,
        unit="rpm",
        expected_frequency_hz=50.0,
        subsystem=Subsystem.ENGINE.value,
        dashboard_gauge="rpm_gauge",
        default_value=0.0,
    )

    # --- 0x102: Fuel Level ---
    FUEL = SignalConfig(
        name="fuel",
        can_id=CANId.FUEL,
        display_name="Fuel Level",
        start_bit=0,
        bit_length=8,
        byte_order="little_endian",
        is_signed=False,
        factor=0.5,
        offset=0.0,
        min_value=0.0,
        max_value=100.0,
        unit="%",
        expected_frequency_hz=1.0,
        subsystem=Subsystem.FUEL.value,
        dashboard_gauge="fuel_gauge",
        default_value=100.0,
    )

    # --- 0x103: Coolant Temperature ---
    TEMP = SignalConfig(
        name="temp",
        can_id=CANId.TEMP,
        display_name="Coolant Temperature",
        start_bit=0,
        bit_length=8,
        byte_order="little_endian",
        is_signed=False,
        factor=1.0,
        offset=-40.0,
        min_value=-40.0,
        max_value=215.0,
        unit="°C",
        expected_frequency_hz=2.0,
        subsystem=Subsystem.COOLING.value,
        dashboard_gauge="temp_gauge",
        default_value=25.0,
    )

    # --- 0x104: Battery Voltage ---
    BATTERY = SignalConfig(
        name="battery",
        can_id=CANId.BATTERY,
        display_name="Battery Voltage",
        start_bit=0,
        bit_length=16,
        byte_order="little_endian",
        is_signed=False,
        factor=0.01,
        offset=0.0,
        min_value=0.0,
        max_value=20.0,
        unit="V",
        expected_frequency_hz=1.0,
        subsystem=Subsystem.BATTERY.value,
        dashboard_gauge="battery_gauge",
        default_value=12.6,
    )

    # --- 0x105: Steering Angle ---
    STEERING = SignalConfig(
        name="steering",
        can_id=CANId.STEERING,
        display_name="Steering Angle",
        start_bit=0,
        bit_length=16,
        byte_order="little_endian",
        is_signed=True,
        factor=0.1,
        offset=0.0,
        min_value=-720.0,
        max_value=720.0,
        unit="deg",
        expected_frequency_hz=20.0,
        subsystem=Subsystem.STEERING.value,
        dashboard_gauge="steering_display",
        default_value=0.0,
    )

    # --- 0x106: Brake Status ---
    BRAKE = SignalConfig(
        name="brake",
        can_id=CANId.BRAKE,
        display_name="Brake Status",
        start_bit=0,
        bit_length=1,
        byte_order="little_endian",
        is_signed=False,
        factor=1.0,
        offset=0.0,
        min_value=0.0,
        max_value=1.0,
        unit="",
        expected_frequency_hz=10.0,
        subsystem=Subsystem.BRAKES.value,
        dashboard_gauge="brake_indicator",
        default_value=0.0,
    )

    # --- 0x107: Accelerator Position ---
    ACCELERATOR = SignalConfig(
        name="accelerator",
        can_id=CANId.ACCELERATOR,
        display_name="Accelerator Position",
        start_bit=0,
        bit_length=8,
        byte_order="little_endian",
        is_signed=False,
        factor=0.5,
        offset=0.0,
        min_value=0.0,
        max_value=100.0,
        unit="%",
        expected_frequency_hz=20.0,
        subsystem=Subsystem.ENGINE.value,
        dashboard_gauge="accelerator_bar",
        default_value=0.0,
    )

    # --- 0x108: Gear Position ---
    GEAR = SignalConfig(
        name="gear",
        can_id=CANId.GEAR,
        display_name="Gear Position",
        start_bit=0,
        bit_length=8,
        byte_order="little_endian",
        is_signed=False,
        factor=1.0,
        offset=0.0,
        min_value=0.0,
        max_value=6.0,
        unit="",
        expected_frequency_hz=0.5,
        subsystem=Subsystem.TRANSMISSION.value,
        dashboard_gauge="gear_indicator",
        default_value=0.0,
    )

    # --- 0x109: Door Status ---
    DOOR = SignalConfig(
        name="door",
        can_id=CANId.DOOR,
        display_name="Door Status",
        start_bit=0,
        bit_length=6,
        byte_order="little_endian",
        is_signed=False,
        factor=1.0,
        offset=0.0,
        min_value=0.0,
        max_value=63.0,
        unit="",
        expected_frequency_hz=0.5,
        subsystem=Subsystem.BODY.value,
        dashboard_gauge="door_status",
        default_value=0.0,
    )

    # --- 0x10A: Indicators ---
    INDICATORS = SignalConfig(
        name="indicator",
        can_id=CANId.INDICATORS,
        display_name="Turn Indicators",
        start_bit=0,
        bit_length=3,
        byte_order="little_endian",
        is_signed=False,
        factor=1.0,
        offset=0.0,
        min_value=0.0,
        max_value=7.0,
        unit="",
        expected_frequency_hz=2.0,
        subsystem=Subsystem.BODY.value,
        dashboard_gauge="turn_indicators",
        default_value=0.0,
    )

    # --- 0x10B: Headlights ---
    HEADLIGHTS = SignalConfig(
        name="headlight",
        can_id=CANId.HEADLIGHTS,
        display_name="Headlights",
        start_bit=0,
        bit_length=3,
        byte_order="little_endian",
        is_signed=False,
        factor=1.0,
        offset=0.0,
        min_value=0.0,
        max_value=7.0,
        unit="",
        expected_frequency_hz=1.0,
        subsystem=Subsystem.ELECTRICAL.value,
        dashboard_gauge="headlight_indicator",
        default_value=0.0,
    )

    # --- 0x10C: Wheel Speeds ---
    WHEEL_SPEED = SignalConfig(
        name="wheel_speed",
        can_id=CANId.WHEEL_SPEED,
        display_name="Wheel Speeds",
        start_bit=0,
        bit_length=64,  # 4 × 16-bit
        byte_order="little_endian",
        is_signed=False,
        factor=0.01,
        offset=0.0,
        min_value=0.0,
        max_value=300.0,
        unit="km/h",
        expected_frequency_hz=20.0,
        subsystem=Subsystem.WHEELS.value,
        dashboard_gauge="",
        default_value=0.0,
    )

    # --- 0x10D: Engine Load ---
    ENGINE_LOAD = SignalConfig(
        name="engine_load",
        can_id=CANId.ENGINE_LOAD,
        display_name="Engine Load",
        start_bit=0,
        bit_length=8,
        byte_order="little_endian",
        is_signed=False,
        factor=0.5,
        offset=0.0,
        min_value=0.0,
        max_value=100.0,
        unit="%",
        expected_frequency_hz=10.0,
        subsystem=Subsystem.ENGINE.value,
        dashboard_gauge="",
        default_value=0.0,
    )

    # --- 0x10E: Ambient Temperature ---
    AMBIENT_TEMP = SignalConfig(
        name="ambient_temp",
        can_id=CANId.AMBIENT_TEMP,
        display_name="Ambient Temperature",
        start_bit=0,
        bit_length=8,
        byte_order="little_endian",
        is_signed=False,
        factor=1.0,
        offset=-40.0,
        min_value=-40.0,
        max_value=85.0,
        unit="°C",
        expected_frequency_hz=0.2,
        subsystem=Subsystem.BODY.value,
        dashboard_gauge="",
        default_value=25.0,
    )

    # --- 0x10F: Odometer ---
    ODOMETER = SignalConfig(
        name="odometer",
        can_id=CANId.ODOMETER,
        display_name="Odometer",
        start_bit=0,
        bit_length=32,
        byte_order="little_endian",
        is_signed=False,
        factor=0.1,
        offset=0.0,
        min_value=0.0,
        max_value=429496729.5,
        unit="km",
        expected_frequency_hz=0.2,
        subsystem=Subsystem.BODY.value,
        dashboard_gauge="",
        default_value=0.0,
    )

    @classmethod
    def get_all(cls) -> Dict[str, SignalConfig]:
        """Get all Phase 1 signal configurations as a dictionary."""
        return {
            "speed": cls.SPEED,
            "rpm": cls.RPM,
            "fuel": cls.FUEL,
            "temp": cls.TEMP,
            "battery": cls.BATTERY,
            "steering": cls.STEERING,
            "brake": cls.BRAKE,
            "accelerator": cls.ACCELERATOR,
            "gear": cls.GEAR,
            "door": cls.DOOR,
            "indicator": cls.INDICATORS,
            "headlight": cls.HEADLIGHTS,
            "wheel_speed": cls.WHEEL_SPEED,
            "engine_load": cls.ENGINE_LOAD,
            "ambient_temp": cls.AMBIENT_TEMP,
            "odometer": cls.ODOMETER,
        }

    @classmethod
    def get_by_can_id(cls, can_id: int) -> List[SignalConfig]:
        """Get all signals for a given CAN ID."""
        return [sig for sig in cls.get_all().values() if sig.can_id == can_id]


# ============================================================================
# SIGNAL LOOKUP FUNCTIONS
# ============================================================================

# Pre-built lookup cache
_SIGNAL_BY_NAME: Dict[str, SignalConfig] = Phase1Signals.get_all()
_SIGNAL_BY_CAN_ID: Dict[int, List[SignalConfig]] = {}

for _sig in _SIGNAL_BY_NAME.values():
    if _sig.can_id not in _SIGNAL_BY_CAN_ID:
        _SIGNAL_BY_CAN_ID[_sig.can_id] = []
    _SIGNAL_BY_CAN_ID[_sig.can_id].append(_sig)


def get_signal_config(name: str) -> Optional[SignalConfig]:
    """
    Get signal configuration by name.

    Args:
        name: Signal name (e.g., "speed", "rpm", "temp")

    Returns:
        SignalConfig or None if not found.
    """
    return _SIGNAL_BY_NAME.get(name)


def get_signals_for_can_id(can_id: int) -> List[SignalConfig]:
    """
    Get all signal configurations for a CAN ID.

    Args:
        can_id: CAN arbitration ID (e.g., 0x100)

    Returns:
        List of SignalConfig for that message.
    """
    return _SIGNAL_BY_CAN_ID.get(can_id, [])


def get_all_signal_names() -> List[str]:
    """Get list of all defined signal names."""
    return list(_SIGNAL_BY_NAME.keys())


def get_gear_mapping() -> Dict[int, str]:
    """Get gear integer-to-string mapping."""
    return {
        0: "P", 1: "R", 2: "N", 3: "D",
        4: "S", 5: "L", 6: "M",
    }


def get_door_bit_labels() -> Dict[int, str]:
    """Get door bitmask bit labels."""
    return {
        0: "FL",    # Front Left
        1: "FR",    # Front Right
        2: "RL",    # Rear Left
        3: "RR",    # Rear Right
        4: "Hood",
        5: "Trunk",
    }