"""
============================================================================
AutoTwin AI - Vehicle State Dataclass
============================================================================
Complete vehicle state representation — the Python-side digital twin.

This is the canonical state object that ALL modules read from:
  - Dashboard reads speed, RPM, fuel, temp
  - 3D Twin reads doors, lights, steering, brake
  - Diagnostics reads all signals for fault evaluation
  - Health Calculator reads all signals for scoring

Design:
  - Nested dataclasses per subsystem
  - All fields have safe defaults
  - to_dict() for WebSocket serialization
  - Validation methods per subsystem
  - Change tracking via sequence numbers

Thread Safety:
  This object is NOT thread-safe by itself.
  Access is synchronized by VehicleStateManager (asyncio lock).
============================================================================
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from app.core.constants import GearPosition, Subsystem


# ============================================================================
# SUBSYSTEM STATE DATACLASSES
# ============================================================================


@dataclass
class EngineState:
    """Engine subsystem state."""

    rpm: int = 0
    coolant_temp: float = 25.0
    oil_temp: float = 25.0
    oil_pressure: float = 0.0
    load: float = 0.0
    throttle_pos: float = 0.0
    fuel_pressure: float = 3.0
    engine_on: bool = False
    misfire_count: int = 0
    runtime_seconds: float = 0.0

    # Derived / computed
    power_estimate: float = 0.0  # kW (estimated from RPM + load)
    torque_estimate: float = 0.0  # Nm

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_overheating(self) -> bool:
        return self.coolant_temp > 105.0

    @property
    def is_redline(self) -> bool:
        return self.rpm > 6500

    @property
    def is_idling(self) -> bool:
        return self.engine_on and 600 <= self.rpm <= 1200 and self.load < 5


@dataclass
class TransmissionState:
    """Transmission subsystem state."""

    gear: str = "P"
    gear_number: int = 0
    gear_ratio: float = 0.0
    torque_lockup: bool = False
    slip_ratio: float = 0.0
    shift_quality: float = 100.0  # % (100 = perfect)
    cvt_ratio: float = 0.0  # For CVT transmissions

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_in_gear(self) -> bool:
        return self.gear not in ("P", "N", "?")

    @property
    def is_reversing(self) -> bool:
        return self.gear == "R"


@dataclass
class BrakeState:
    """Brake subsystem state."""

    applied: bool = False
    pedal_position: float = 0.0  # % [0..100]
    pressure: float = 0.0  # bar [0..200]
    abs_active: bool = False
    esp_active: bool = False
    parking_brake: bool = True

    # Pad wear (% remaining, 100 = new)
    pad_wear_fl: float = 100.0
    pad_wear_fr: float = 100.0
    pad_wear_rl: float = 100.0
    pad_wear_rr: float = 100.0

    # Disc temperature (°C, estimated)
    disc_temp_fl: float = 25.0
    disc_temp_fr: float = 25.0
    disc_temp_rl: float = 25.0
    disc_temp_rr: float = 25.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def min_pad_wear(self) -> float:
        return min(self.pad_wear_fl, self.pad_wear_fr,
                   self.pad_wear_rl, self.pad_wear_rr)

    @property
    def avg_pad_wear(self) -> float:
        return (self.pad_wear_fl + self.pad_wear_fr +
                self.pad_wear_rl + self.pad_wear_rr) / 4.0

    @property
    def pads_critical(self) -> bool:
        return self.min_pad_wear < 10.0


@dataclass
class CoolingState:
    """Cooling system state."""

    coolant_temp: float = 25.0
    fan_active: bool = False
    fan_speed: float = 0.0  # % [0..100]
    thermostat_open: bool = False
    flow_rate: float = 0.0  # L/min
    radiator_temp_in: float = 25.0
    radiator_temp_out: float = 25.0
    coolant_level: float = 100.0  # %

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_overheating(self) -> bool:
        return self.coolant_temp > 105.0

    @property
    def is_critical(self) -> bool:
        return self.coolant_temp > 120.0

    @property
    def fan_should_be_on(self) -> bool:
        """Fan should activate above 95°C."""
        return self.coolant_temp > 95.0


@dataclass
class BatteryState:
    """Battery and charging system state."""

    voltage: float = 12.6
    current: float = 0.0  # A (+ = charging, - = discharging)
    soc: float = 100.0  # State of charge %
    health: float = 100.0  # Battery health %
    charging: bool = True
    temperature: float = 25.0
    alternator_output: float = 14.0  # V
    internal_resistance: float = 5.0  # mΩ

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_low(self) -> bool:
        return self.voltage < 11.5

    @property
    def is_critical(self) -> bool:
        return self.voltage < 10.5

    @property
    def is_overcharging(self) -> bool:
        return self.voltage > 15.0

    @property
    def power_draw_watts(self) -> float:
        return abs(self.voltage * self.current)


@dataclass
class BodyState:
    """Body, doors, and lighting state."""

    speed: float = 0.0  # km/h
    door_fl: bool = False  # True = open
    door_fr: bool = False
    door_rl: bool = False
    door_rr: bool = False
    hood: bool = False
    trunk: bool = False

    headlights_low: bool = False
    headlights_high: bool = False
    fog_lights: bool = False
    turn_left: bool = False
    turn_right: bool = False
    hazard: bool = False

    seatbelt_driver: bool = False
    seatbelt_passenger: bool = False
    odometer: float = 0.0  # km
    ambient_temp: float = 25.0  # °C

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def any_door_open(self) -> bool:
        return any([self.door_fl, self.door_fr,
                    self.door_rl, self.door_rr,
                    self.hood, self.trunk])

    @property
    def open_doors_list(self) -> List[str]:
        doors = []
        if self.door_fl: doors.append("FL")
        if self.door_fr: doors.append("FR")
        if self.door_rl: doors.append("RL")
        if self.door_rr: doors.append("RR")
        if self.hood: doors.append("Hood")
        if self.trunk: doors.append("Trunk")
        return doors

    @property
    def is_moving(self) -> bool:
        return self.speed > 0.5

    @property
    def lights_on(self) -> bool:
        return self.headlights_low or self.headlights_high


@dataclass
class SteeringState:
    """Steering system state."""

    angle: float = 0.0  # degrees [-720..720]
    rate: float = 0.0  # deg/s
    torque: float = 0.0  # Nm (driver input torque)
    power_assist: bool = True
    eps_mode: int = 1  # 0=Comfort, 1=Normal, 2=Sport
    wheel_angle: float = 0.0  # Actual wheel angle (angle / steering_ratio)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def steering_ratio(self) -> float:
        return 14.5  # Typical passenger car

    @property
    def is_turning(self) -> bool:
        return abs(self.angle) > 5.0


@dataclass
class FuelState:
    """Fuel system state."""

    level: float = 100.0  # %
    pressure: float = 3.0  # bar
    consumption_rate: float = 0.0  # L/100km (instant)
    avg_consumption: float = 7.5  # L/100km (average)
    range_km: float = 600.0  # Estimated range
    tank_capacity: float = 50.0  # Liters

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def is_low(self) -> bool:
        return self.level < 15.0

    @property
    def is_critical(self) -> bool:
        return self.level < 5.0

    @property
    def liters_remaining(self) -> float:
        return self.tank_capacity * (self.level / 100.0)


@dataclass
class ElectricalState:
    """Electrical system state."""

    bus_voltage: float = 12.6  # V
    alternator_voltage: float = 14.0  # V
    total_load: float = 0.0  # A
    accessory_load: float = 0.0  # A
    ground_fault: bool = False
    fuse_blown: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WheelSpeedState:
    """Individual wheel speed sensors."""

    fl: float = 0.0  # Front Left (km/h)
    fr: float = 0.0  # Front Right
    rl: float = 0.0  # Rear Left
    rr: float = 0.0  # Rear Right

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def average(self) -> float:
        return (self.fl + self.fr + self.rl + self.rr) / 4.0

    @property
    def max_difference(self) -> float:
        speeds = [self.fl, self.fr, self.rl, self.rr]
        return max(speeds) - min(speeds)

    @property
    def has_wheel_slip(self) -> bool:
        """Detect if any wheel is significantly different (slip/lock)."""
        return self.max_difference > 10.0


# ============================================================================
# COMPLETE VEHICLE STATE
# ============================================================================


@dataclass
class VehicleState:
    """
    Complete vehicle state — the digital twin representation.

    This is the SINGLE object that represents the entire vehicle.
    All modules read from this. Only StateUpdater writes to it.

    Memory: ~500 bytes (all primitive types)
    """

    # Subsystem states
    engine: EngineState = field(default_factory=EngineState)
    transmission: TransmissionState = field(default_factory=TransmissionState)
    brakes: BrakeState = field(default_factory=BrakeState)
    cooling: CoolingState = field(default_factory=CoolingState)
    battery: BatteryState = field(default_factory=BatteryState)
    body: BodyState = field(default_factory=BodyState)
    steering: SteeringState = field(default_factory=SteeringState)
    fuel: FuelState = field(default_factory=FuelState)
    electrical: ElectricalState = field(default_factory=ElectricalState)
    wheel_speed: WheelSpeedState = field(default_factory=WheelSpeedState)

    # Metadata
    vehicle_id: str = ""
    vehicle_name: str = "Unknown Vehicle"
    session_start: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    frame_count: int = 0
    sequence: int = 0
    can_active: bool = False
    data_source: str = "unknown"

    # Health (computed by HealthCalculator)
    overall_health: float = 100.0
    active_fault_count: int = 0

    # ========================================================================
    # SERIALIZATION
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to flat dictionary for WebSocket broadcast.

        This is the format sent to the frontend at 20 Hz.
        """
        return {
            # Engine
            "speed": self.body.speed,
            "rpm": self.engine.rpm,
            "fuel": self.fuel.level,
            "temp": self.engine.coolant_temp,
            "battery": self.battery.voltage,
            "steering": self.steering.angle,
            "brake": 1 if self.brakes.applied else 0,
            "accelerator": self.engine.throttle_pos,
            "gear": self.transmission.gear,
            "door": self._door_status_string(),
            "indicator": self._indicator_value(),
            "headlight": self._headlight_value(),
            "engine_load": self.engine.load,
            "ambient_temp": self.body.ambient_temp,
            "odometer": self.body.odometer,

            # Detailed (for expanded panels)
            "engine": self.engine.to_dict(),
            "transmission": self.transmission.to_dict(),
            "brakes": self.brakes.to_dict(),
            "cooling": self.cooling.to_dict(),
            "battery_detail": self.battery.to_dict(),
            "body": self.body.to_dict(),
            "steering_detail": self.steering.to_dict(),
            "fuel_detail": self.fuel.to_dict(),
            "wheel_speed": self.wheel_speed.to_dict(),

            # Metadata
            "frame_count": self.frame_count,
            "can_active": self.can_active,
            "uptime": time.time() - self.session_start,
            "sequence": self.sequence,
            "overall_health": self.overall_health,
            "active_faults": self.active_fault_count,
            "timestamp": time.time(),
        }

    def to_compact_dict(self) -> Dict[str, Any]:
        """
        Compact format for high-frequency broadcast (minimal bandwidth).
        Only includes primary signals.
        """
        return {
            "speed": self.body.speed,
            "rpm": self.engine.rpm,
            "fuel": self.fuel.level,
            "temp": self.engine.coolant_temp,
            "battery": self.battery.voltage,
            "steering": self.steering.angle,
            "brake": 1 if self.brakes.applied else 0,
            "accelerator": self.engine.throttle_pos,
            "gear": self.transmission.gear,
            "door": self._door_status_string(),
            "indicator": self._indicator_value(),
            "headlight": self._headlight_value(),
            "engine_load": self.engine.load,
            "seq": self.sequence,
        }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _door_status_string(self) -> str:
        """Convert door booleans to display string."""
        if not self.body.any_door_open:
            return "Closed"
        return " ".join(self.body.open_doors_list)

    def _indicator_value(self) -> int:
        """Convert indicator booleans to bitmask."""
        val = 0
        if self.body.turn_left: val |= 1
        if self.body.turn_right: val |= 2
        if self.body.hazard: val |= 4
        return val

    def _headlight_value(self) -> int:
        """Convert headlight booleans to bitmask."""
        val = 0
        if self.body.headlights_low: val |= 1
        if self.body.headlights_high: val |= 2
        if self.body.fog_lights: val |= 4
        return val

    # ========================================================================
    # STATE QUERIES
    # ========================================================================

    def get_subsystem_state(self, subsystem: str) -> Optional[Dict[str, Any]]:
        """Get state dictionary for a specific subsystem."""
        mapping = {
            Subsystem.ENGINE.value: self.engine,
            Subsystem.TRANSMISSION.value: self.transmission,
            Subsystem.BRAKES.value: self.brakes,
            Subsystem.COOLING.value: self.cooling,
            Subsystem.BATTERY.value: self.battery,
            Subsystem.BODY.value: self.body,
            Subsystem.STEERING.value: self.steering,
            Subsystem.FUEL.value: self.fuel,
            Subsystem.ELECTRICAL.value: self.electrical,
        }
        state = mapping.get(subsystem)
        return state.to_dict() if state else None

    @property
    def is_operational(self) -> bool:
        """Vehicle is running and drivable."""
        return (
            self.engine.engine_on
            and not self.engine.is_overheating
            and not self.battery.is_critical
            and self.can_active
        )

    @property
    def has_critical_issues(self) -> bool:
        """Vehicle has critical issues requiring immediate attention."""
        return (
            self.engine.coolant_temp > 120
            or self.battery.voltage < 10.5
            or self.brakes.pads_critical
        )

    def get_warnings(self) -> List[str]:
        """Get list of active warning messages."""
        warnings = []

        if self.engine.is_overheating:
            warnings.append(f"Engine overheating: {self.engine.coolant_temp:.0f}°C")
        if self.battery.is_low:
            warnings.append(f"Low battery: {self.battery.voltage:.1f}V")
        if self.fuel.is_low:
            warnings.append(f"Low fuel: {self.fuel.level:.0f}%")
        if self.body.any_door_open and self.body.is_moving:
            warnings.append("Door open while moving!")
        if self.brakes.pads_critical:
            warnings.append("Brake pads critically worn")
        if self.engine.is_redline:
            warnings.append(f"RPM in redline: {self.engine.rpm}")

        return warnings

    # ========================================================================
    # RESET
    # ========================================================================

    def reset(self) -> None:
        """Reset all state to defaults."""
        self.engine = EngineState()
        self.transmission = TransmissionState()
        self.brakes = BrakeState()
        self.cooling = CoolingState()
        self.battery = BatteryState()
        self.body = BodyState()
        self.steering = SteeringState()
        self.fuel = FuelState()
        self.electrical = ElectricalState()
        self.wheel_speed = WheelSpeedState()
        self.frame_count = 0
        self.sequence = 0
        self.can_active = False
        self.overall_health = 100.0
        self.active_fault_count = 0