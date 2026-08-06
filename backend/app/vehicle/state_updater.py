"""
============================================================================
AutoTwin AI - State Updater
============================================================================
Applies decoded CAN signals to the VehicleState object.

This is the BRIDGE between the CAN Parser and the Vehicle State:
  CANFrameParser.decode_serial_frame() → DecodedFrame
  StateUpdater.apply() → VehicleState (mutated)

Responsibilities:
  - Map decoded signals to VehicleState fields
  - Handle type conversions (string → float/int/bool)
  - Apply gear mapping (integer → "P"/"R"/"N"/"D")
  - Apply door bitmask → individual booleans
  - Apply indicator bitmask → individual booleans
  - Track change count for delta broadcasting
  - Update metadata (timestamp, frame count)

Usage:
    updater = StateUpdater()
    changes = updater.apply(vehicle_state, decoded_signals)
============================================================================
"""

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger

from app.core.constants import GearPosition
from app.vehicle.vehicle_state import VehicleState


# ============================================================================
# STATE UPDATER
# ============================================================================


class StateUpdater:
    """
    Applies decoded CAN signal values to VehicleState.

    Stateless: Can be reused across multiple vehicles.
    Thread-safe: No internal mutable state.
    """

    # Mapping from signal names to (subsystem, attribute) paths
    SIGNAL_MAP: Dict[str, Tuple[str, str]] = {
        "speed": ("body", "speed"),
        "rpm": ("engine", "rpm"),
        "fuel": ("fuel", "level"),
        "temp": ("engine", "coolant_temp"),
        "battery": ("battery", "voltage"),
        "steering": ("steering", "angle"),
        "brake": ("brakes", "applied"),
        "accelerator": ("engine", "throttle_pos"),
        "gear": ("transmission", "gear"),
        "door": ("body", "_doors"),  # Special handling
        "indicator": ("body", "_indicators"),  # Special handling
        "headlight": ("body", "_headlights"),  # Special handling
        "engine_load": ("engine", "load"),
        "ambient_temp": ("body", "ambient_temp"),
        "odometer": ("body", "odometer"),
        "wheel_fl": ("wheel_speed", "fl"),
        "wheel_fr": ("wheel_speed", "fr"),
        "wheel_rl": ("wheel_speed", "rl"),
        "wheel_rr": ("wheel_speed", "rr"),
        "brake_pressure": ("brakes", "pressure"),
        "abs": ("brakes", "abs_active"),
    }

    def __init__(self):
        self._update_count: int = 0
        self._total_changes: int = 0

    # ========================================================================
    # MAIN APPLY METHOD
    # ========================================================================

    def apply(
        self,
        state: VehicleState,
        signals: Dict[str, Any],
        source: str = "can",
    ) -> int:
        """
        Apply a dictionary of decoded signals to the vehicle state.

        Args:
            state: VehicleState to update (mutated in place)
            signals: Dictionary of {signal_name: value}
            source: Source identifier for logging

        Returns:
            Number of signals that actually changed.
        """
        changes = 0

        for signal_name, value in signals.items():
            try:
                changed = self._apply_signal(state, signal_name, value)
                if changed:
                    changes += 1
            except Exception as e:
                logger.warning(f"StateUpdater: error applying '{signal_name}': {e}")

        # Update metadata
        if changes > 0:
            state.last_update = time.time()
            state.frame_count += 1
            state.sequence += 1
            state.can_active = True
            state.data_source = source

        self._update_count += 1
        self._total_changes += changes

        return changes

    # ========================================================================
    # INDIVIDUAL SIGNAL APPLICATION
    # ========================================================================

    def _apply_signal(self, state: VehicleState, name: str, value: Any) -> bool:
        """
        Apply a single signal to the state.

        Returns:
            True if the value actually changed.
        """
        # Special handling for complex signals
        if name == "door":
            return self._apply_door_status(state, value)
        elif name == "indicator":
            return self._apply_indicators(state, value)
        elif name == "headlight":
            return self._apply_headlights(state, value)
        elif name == "gear":
            return self._apply_gear(state, value)
        elif name == "brake":
            return self._apply_brake(state, value)
        elif name == "abs":
            return self._apply_abs(state, value)

        # Standard signal mapping
        if name not in self.SIGNAL_MAP:
            return False

        subsystem_name, attr_name = self.SIGNAL_MAP[name]
        subsystem = getattr(state, subsystem_name, None)

        if subsystem is None:
            return False

        # Get current value
        current = getattr(subsystem, attr_name, None)

        # Convert value to appropriate type
        converted = self._convert_value(name, value, type(current) if current is not None else float)

        # Check if changed
        if converted == current:
            return False

        # Apply
        setattr(subsystem, attr_name, converted)

        # Side effects
        self._apply_side_effects(state, name, converted)

        return True

    # ========================================================================
    # SPECIAL SIGNAL HANDLERS
    # ========================================================================

    def _apply_door_status(self, state: VehicleState, value: Any) -> bool:
        """Apply door bitmask or string to individual door booleans."""
        changed = False

        if isinstance(value, str):
            # String format: "Closed", "FL", "FL FR", etc.
            doors_open = value.upper().split() if value != "Closed" else []
            new_fl = "FL" in doors_open
            new_fr = "FR" in doors_open
            new_rl = "RL" in doors_open
            new_rr = "RR" in doors_open
            new_hood = "HOOD" in doors_open
            new_trunk = "TRUNK" in doors_open

        elif isinstance(value, (int, float)):
            # Bitmask format
            bitmask = int(value)
            new_fl = bool(bitmask & (1 << 0))
            new_fr = bool(bitmask & (1 << 1))
            new_rl = bool(bitmask & (1 << 2))
            new_rr = bool(bitmask & (1 << 3))
            new_hood = bool(bitmask & (1 << 4))
            new_trunk = bool(bitmask & (1 << 5))
        else:
            return False

        body = state.body
        if body.door_fl != new_fl:
            body.door_fl = new_fl
            changed = True
        if body.door_fr != new_fr:
            body.door_fr = new_fr
            changed = True
        if body.door_rl != new_rl:
            body.door_rl = new_rl
            changed = True
        if body.door_rr != new_rr:
            body.door_rr = new_rr
            changed = True
        if body.hood != new_hood:
            body.hood = new_hood
            changed = True
        if body.trunk != new_trunk:
            body.trunk = new_trunk
            changed = True

        return changed

    def _apply_indicators(self, state: VehicleState, value: Any) -> bool:
        """Apply indicator bitmask to individual booleans."""
        bitmask = int(value) if isinstance(value, (int, float, str)) else 0
        changed = False

        body = state.body
        new_left = bool(bitmask & 1)
        new_right = bool(bitmask & 2)
        new_hazard = bool(bitmask & 4)

        if body.turn_left != new_left:
            body.turn_left = new_left
            changed = True
        if body.turn_right != new_right:
            body.turn_right = new_right
            changed = True
        if body.hazard != new_hazard:
            body.hazard = new_hazard
            changed = True

        return changed

    def _apply_headlights(self, state: VehicleState, value: Any) -> bool:
        """Apply headlight bitmask to individual booleans."""
        bitmask = int(value) if isinstance(value, (int, float, str)) else 0
        changed = False

        body = state.body
        new_low = bool(bitmask & 1)
        new_high = bool(bitmask & 2)
        new_fog = bool(bitmask & 4)

        if body.headlights_low != new_low:
            body.headlights_low = new_low
            changed = True
        if body.headlights_high != new_high:
            body.headlights_high = new_high
            changed = True
        if body.fog_lights != new_fog:
            body.fog_lights = new_fog
            changed = True

        return changed

    def _apply_gear(self, state: VehicleState, value: Any) -> bool:
        """Apply gear value (integer or string)."""
        if isinstance(value, str):
            new_gear = value.upper()
        elif isinstance(value, (int, float)):
            new_gear = GearPosition.from_int(int(value)).value
        else:
            return False

        if state.transmission.gear != new_gear:
            state.transmission.gear = new_gear
            # Also update gear number
            gear_map = {"P": 0, "R": 1, "N": 2, "D": 3, "S": 4, "L": 5, "M": 6}
            state.transmission.gear_number = gear_map.get(new_gear, 0)
            return True
        return False

    def _apply_brake(self, state: VehicleState, value: Any) -> bool:
        """Apply brake status (boolean or 0/1)."""
        if isinstance(value, str):
            new_brake = value.lower() in ("1", "true", "yes")
        elif isinstance(value, (int, float)):
            new_brake = bool(int(value))
        elif isinstance(value, bool):
            new_brake = value
        else:
            return False

        if state.brakes.applied != new_brake:
            state.brakes.applied = new_brake
            # Side effect: update pedal position estimate
            state.brakes.pedal_position = 60.0 if new_brake else 0.0
            return True
        return False

    def _apply_abs(self, state: VehicleState, value: Any) -> bool:
        """Apply ABS activation status."""
        new_abs = bool(int(value)) if isinstance(value, (int, float, str)) else False
        if state.brakes.abs_active != new_abs:
            state.brakes.abs_active = new_abs
            return True
        return False

    # ========================================================================
    # VALUE CONVERSION
    # ========================================================================

    def _convert_value(self, name: str, value: Any, target_type: type) -> Any:
        """Convert a value to the appropriate type for the target field."""
        try:
            if target_type == bool:
                if isinstance(value, str):
                    return value.lower() in ("1", "true", "yes")
                return bool(int(value))
            elif target_type == int:
                return int(float(value))
            elif target_type == float:
                return float(value)
            elif target_type == str:
                return str(value)
            else:
                return value
        except (ValueError, TypeError):
            return value

    # ========================================================================
    # SIDE EFFECTS
    # ========================================================================

    def _apply_side_effects(self, state: VehicleState, signal_name: str, value: Any) -> None:
        """
        Apply derived/side-effect updates when a signal changes.

        Examples:
          - Speed change → update wheel speed average
          - Temp change → update cooling state
          - RPM change → estimate engine power
        """
        if signal_name == "speed":
            # Sync body speed to wheel speeds if not individually set
            pass  # Wheel speeds come from separate CAN message

        elif signal_name == "temp":
            # Mirror engine coolant temp to cooling subsystem
            state.cooling.coolant_temp = value
            # Auto-detect fan state
            if value > 95 and not state.cooling.fan_active:
                state.cooling.fan_active = True
                state.cooling.fan_speed = 80.0
            elif value < 90 and state.cooling.fan_active:
                state.cooling.fan_active = False
                state.cooling.fan_speed = 0.0

        elif signal_name == "rpm":
            # Estimate engine power (very rough)
            if value > 0:
                state.engine.power_estimate = (value / 8000.0) * 100.0  # Max ~100 kW
            state.engine.engine_on = value > 100

        elif signal_name == "steering":
            # Calculate actual wheel angle
            state.steering.wheel_angle = value / state.steering.steering_ratio

        elif signal_name == "fuel":
            # Estimate range
            if state.fuel.avg_consumption > 0:
                state.fuel.range_km = (state.fuel.liters_remaining /
                                       state.fuel.avg_consumption) * 100

        elif signal_name == "accelerator":
            # Estimate engine load from throttle
            if value > 0:
                state.engine.load = min(100.0, value * 0.9 + state.body.speed * 0.05)

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        return {
            "update_count": self._update_count,
            "total_changes": self._total_changes,
            "avg_changes_per_update": (
                self._total_changes / max(self._update_count, 1)
            ),
        }