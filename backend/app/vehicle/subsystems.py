"""
============================================================================
AutoTwin AI - Vehicle Subsystem Definitions
============================================================================
Defines each vehicle subsystem with its signals, thresholds,
3D positions, and diagnostic context.

Each subsystem:
  - Knows which signals belong to it
  - Has warning/critical thresholds
  - Maps to a 3D position for highlighting
  - Provides diagnostic context for the fault engine
  - Has a health calculation method

Usage:
    registry = get_subsystem_registry()
    engine = registry.get("engine")
    engine.check_thresholds(state)  # Returns list of violations
============================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.core.constants import Subsystem, DefaultThresholds
from app.vehicle.vehicle_state import VehicleState


# ============================================================================
# SUBSYSTEM BASE CLASS
# ============================================================================


class SubsystemBase(ABC):
    """
    Abstract base class for all vehicle subsystems.

    Each subsystem defines:
      - Which signals it monitors
      - Warning and critical thresholds
      - 3D position for visualization
      - Health calculation logic
      - Diagnostic messages
    """

    def __init__(self):
        self._violations: List[Dict[str, Any]] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Subsystem identifier."""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name."""
        ...

    @property
    @abstractmethod
    def monitored_signals(self) -> List[str]:
        """List of signal names this subsystem monitors."""
        ...

    @property
    def position_3d(self) -> Tuple[float, float, float]:
        """3D position for highlighting in the digital twin."""
        return (0.0, 0.0, 0.0)

    @property
    def color(self) -> str:
        """Display color for this subsystem."""
        return "#00d4ff"

    @abstractmethod
    def check_thresholds(self, state: VehicleState) -> List[Dict[str, Any]]:
        """
        Check all thresholds for this subsystem.

        Returns:
            List of threshold violations:
            [{"signal": "temp", "value": 112, "threshold": 105,
              "severity": "HIGH", "message": "Coolant temperature high"}]
        """
        ...

    def get_diagnostic_context(self, state: VehicleState) -> Dict[str, Any]:
        """Get diagnostic-relevant data for this subsystem."""
        return {}

    def reset_violations(self) -> None:
        self._violations.clear()


# ============================================================================
# ENGINE SUBSYSTEM
# ============================================================================


class EngineSubsystem(SubsystemBase):
    """Engine subsystem: RPM, temperature, load, throttle."""

    @property
    def name(self) -> str:
        return Subsystem.ENGINE.value

    @property
    def display_name(self) -> str:
        return "Engine"

    @property
    def monitored_signals(self) -> List[str]:
        return ["rpm", "temp", "engine_load", "accelerator", "oil_pressure"]

    @property
    def position_3d(self) -> Tuple[float, float, float]:
        return (0.0, 0.3, 1.2)  # Front-center of vehicle

    @property
    def color(self) -> str:
        return "#ff6b35"

    def check_thresholds(self, state: VehicleState) -> List[Dict[str, Any]]:
        violations = []
        engine = state.engine

        # RPM redline
        if engine.rpm > DefaultThresholds.RPM_REDLINE:
            violations.append({
                "signal": "rpm",
                "value": engine.rpm,
                "threshold": DefaultThresholds.RPM_REDLINE,
                "severity": "HIGH",
                "message": f"Engine RPM in redline zone ({engine.rpm} rpm)",
                "subsystem": self.name,
            })

        # Coolant temperature
        if engine.coolant_temp > DefaultThresholds.TEMP_CRITICAL:
            violations.append({
                "signal": "temp",
                "value": engine.coolant_temp,
                "threshold": DefaultThresholds.TEMP_CRITICAL,
                "severity": "CRITICAL",
                "message": f"Engine critically overheated ({engine.coolant_temp:.0f}°C)",
                "subsystem": self.name,
            })
        elif engine.coolant_temp > DefaultThresholds.TEMP_HIGH:
            violations.append({
                "signal": "temp",
                "value": engine.coolant_temp,
                "threshold": DefaultThresholds.TEMP_HIGH,
                "severity": "HIGH",
                "message": f"Engine overheating ({engine.coolant_temp:.0f}°C)",
                "subsystem": self.name,
            })

        # High engine load
        if engine.load > DefaultThresholds.LOAD_HIGH:
            violations.append({
                "signal": "engine_load",
                "value": engine.load,
                "threshold": DefaultThresholds.LOAD_HIGH,
                "severity": "MEDIUM",
                "message": f"High engine load ({engine.load:.0f}%)",
                "subsystem": self.name,
            })

        self._violations = violations
        return violations

    def get_diagnostic_context(self, state: VehicleState) -> Dict[str, Any]:
        engine = state.engine
        return {
            "rpm": engine.rpm,
            "coolant_temp": engine.coolant_temp,
            "oil_temp": engine.oil_temp,
            "load": engine.load,
            "throttle": engine.throttle_pos,
            "runtime_s": engine.runtime_seconds,
            "is_overheating": engine.is_overheating,
            "is_redline": engine.is_redline,
        }


# ============================================================================
# BRAKE SUBSYSTEM
# ============================================================================


class BrakeSubsystem(SubsystemBase):
    """Brake subsystem: pedal, pressure, ABS, pad wear."""

    @property
    def name(self) -> str:
        return Subsystem.BRAKES.value

    @property
    def display_name(self) -> str:
        return "Brakes"

    @property
    def monitored_signals(self) -> List[str]:
        return ["brake", "brake_pressure", "abs", "wheel_fl", "wheel_fr", "wheel_rl", "wheel_rr"]

    @property
    def position_3d(self) -> Tuple[float, float, float]:
        return (0.0, -0.3, 0.0)  # Under vehicle

    @property
    def color(self) -> str:
        return "#ff3333"

    def check_thresholds(self, state: VehicleState) -> List[Dict[str, Any]]:
        violations = []
        brakes = state.brakes

        # Pad wear
        if brakes.min_pad_wear < 10:
            violations.append({
                "signal": "pad_wear",
                "value": brakes.min_pad_wear,
                "threshold": 10,
                "severity": "HIGH",
                "message": f"Brake pads critically worn ({brakes.min_pad_wear:.0f}% remaining)",
                "subsystem": self.name,
            })
        elif brakes.min_pad_wear < 25:
            violations.append({
                "signal": "pad_wear",
                "value": brakes.min_pad_wear,
                "threshold": 25,
                "severity": "MEDIUM",
                "message": f"Brake pads wearing low ({brakes.min_pad_wear:.0f}% remaining)",
                "subsystem": self.name,
            })

        # ABS activation (informational)
        if brakes.abs_active:
            violations.append({
                "signal": "abs",
                "value": 1,
                "threshold": 0,
                "severity": "INFO",
                "message": "ABS system active",
                "subsystem": self.name,
            })

        # Wheel speed mismatch during braking
        if brakes.applied and state.wheel_speed.has_wheel_slip:
            violations.append({
                "signal": "wheel_speed_diff",
                "value": state.wheel_speed.max_difference,
                "threshold": 10.0,
                "severity": "MEDIUM",
                "message": "Wheel speed mismatch during braking (possible drag)",
                "subsystem": self.name,
            })

        self._violations = violations
        return violations


# ============================================================================
# COOLING SUBSYSTEM
# ============================================================================


class CoolingSubsystem(SubsystemBase):
    """Cooling system: coolant temp, fan, thermostat, flow."""

    @property
    def name(self) -> str:
        return Subsystem.COOLING.value

    @property
    def display_name(self) -> str:
        return "Cooling System"

    @property
    def monitored_signals(self) -> List[str]:
        return ["temp", "fan_speed", "coolant_level"]

    @property
    def position_3d(self) -> Tuple[float, float, float]:
        return (0.0, 0.2, 2.0)  # Front (radiator area)

    @property
    def color(self) -> str:
        return "#00ff88"

    def check_thresholds(self, state: VehicleState) -> List[Dict[str, Any]]:
        violations = []
        cooling = state.cooling

        # Temperature thresholds
        if cooling.coolant_temp > DefaultThresholds.TEMP_CRITICAL:
            violations.append({
                "signal": "coolant_temp",
                "value": cooling.coolant_temp,
                "threshold": DefaultThresholds.TEMP_CRITICAL,
                "severity": "CRITICAL",
                "message": f"CRITICAL: Coolant at {cooling_temp:.0f}°C - engine damage risk",
                "subsystem": self.name,
            })
        elif cooling.coolant_temp > DefaultThresholds.TEMP_HIGH:
            violations.append({
                "signal": "coolant_temp",
                "value": cooling.coolant_temp,
                "threshold": DefaultThresholds.TEMP_HIGH,
                "severity": "HIGH",
                "message": f"Coolant temperature high: {cooling.coolant_temp:.0f}°C",
                "subsystem": self.name,
            })

        # Fan failure detection
        if cooling.fan_should_be_on and not cooling.fan_active:
            violations.append({
                "signal": "fan_status",
                "value": 0,
                "threshold": 1,
                "severity": "HIGH",
                "message": "Radiator fan not activating despite high temperature",
                "subsystem": self.name,
            })

        # Low coolant level
        if cooling.coolant_level < 30:
            violations.append({
                "signal": "coolant_level",
                "value": cooling.coolant_level,
                "threshold": 30,
                "severity": "MEDIUM",
                "message": f"Coolant level low ({cooling.coolant_level:.0f}%)",
                "subsystem": self.name,
            })

        self._violations = violations
        return violations


# ============================================================================
# BATTERY SUBSYSTEM
# ============================================================================


class BatterySubsystem(SubsystemBase):
    """Battery and charging system."""

    @property
    def name(self) -> str:
        return Subsystem.BATTERY.value

    @property
    def display_name(self) -> str:
        return "Battery"

    @property
    def monitored_signals(self) -> List[str]:
        return ["battery"]

    @property
    def position_3d(self) -> Tuple[float, float, float]:
        return (0.5, 0.2, 1.5)  # Engine bay, right side

    @property
    def color(self) -> str:
        return "#eab308"

    def check_thresholds(self, state: VehicleState) -> List[Dict[str, Any]]:
        violations = []
        battery = state.battery

        # Low voltage
        if battery.voltage < DefaultThresholds.BATTERY_CRITICAL:
            violations.append({
                "signal": "battery_voltage",
                "value": battery.voltage,
                "threshold": DefaultThresholds.BATTERY_CRITICAL,
                "severity": "CRITICAL",
                "message": f"Battery critically low: {battery.voltage:.1f}V",
                "subsystem": self.name,
            })
        elif battery.voltage < DefaultThresholds.BATTERY_LOW:
            violations.append({
                "signal": "battery_voltage",
                "value": battery.voltage,
                "threshold": DefaultThresholds.BATTERY_LOW,
                "severity": "HIGH",
                "message": f"Battery voltage low: {battery.voltage:.1f}V",
                "subsystem": self.name,
            })

        # Overcharging
        if battery.voltage > DefaultThresholds.BATTERY_OVERCHARGE:
            violations.append({
                "signal": "battery_voltage",
                "value": battery.voltage,
                "threshold": DefaultThresholds.BATTERY_OVERCHARGE,
                "severity": "HIGH",
                "message": f"Battery overcharging: {battery.voltage:.1f}V",
                "subsystem": self.name,
            })

        self._violations = violations
        return violations


# ============================================================================
# TRANSMISSION SUBSYSTEM
# ============================================================================


class TransmissionSubsystem(SubsystemBase):
    """Transmission: gear, ratios, slip."""

    @property
    def name(self) -> str:
        return Subsystem.TRANSMISSION.value

    @property
    def display_name(self) -> str:
        return "Transmission"

    @property
    def monitored_signals(self) -> List[str]:
        return ["gear", "rpm", "speed"]

    @property
    def position_3d(self) -> Tuple[float, float, float]:
        return (0.0, -0.2, 0.3)  # Center-under vehicle

    @property
    def color(self) -> str:
        return "#6366f1"

    def check_thresholds(self, state: VehicleState) -> List[Dict[str, Any]]:
        violations = []

        # High RPM with low speed (possible slip)
        if (state.transmission.is_in_gear and
                state.engine.rpm > 4000 and
                state.body.speed < 20):
            violations.append({
                "signal": "rpm_speed_ratio",
                "value": state.engine.rpm / max(state.body.speed, 1),
                "threshold": 200,
                "severity": "MEDIUM",
                "message": "High RPM with low speed - possible transmission slip",
                "subsystem": self.name,
            })

        self._violations = violations
        return violations


# ============================================================================
# ELECTRICAL SUBSYSTEM
# ============================================================================


class ElectricalSubsystem(SubsystemBase):
    """Electrical system: bus voltage, loads, grounds."""

    @property
    def name(self) -> str:
        return Subsystem.ELECTRICAL.value

    @property
    def display_name(self) -> str:
        return "Electrical"

    @property
    def monitored_signals(self) -> List[str]:
        return ["battery", "headlight", "indicator"]

    @property
    def position_3d(self) -> Tuple[float, float, float]:
        return (-0.5, 0.3, 0.5)  # Left side of engine bay

    @property
    def color(self) -> str:
        return "#00d4ff"

    def check_thresholds(self, state: VehicleState) -> List[Dict[str, Any]]:
        violations = []

        # Ground fault
        if state.electrical.ground_fault:
            violations.append({
                "signal": "ground_fault",
                "value": 1,
                "threshold": 0,
                "severity": "HIGH",
                "message": "Electrical ground fault detected",
                "subsystem": self.name,
            })

        self._violations = violations
        return violations


# ============================================================================
# SUBSYSTEM REGISTRY
# ============================================================================

# Singleton registry
_SUBSYSTEM_REGISTRY: Dict[str, SubsystemBase] = {}


def get_subsystem_registry() -> Dict[str, SubsystemBase]:
    """
    Get the global subsystem registry.

    Returns:
        Dictionary of {subsystem_name: SubsystemBase instance}
    """
    global _SUBSYSTEM_REGISTRY

    if not _SUBSYSTEM_REGISTRY:
        _SUBSYSTEM_REGISTRY = {
            Subsystem.ENGINE.value: EngineSubsystem(),
            Subsystem.BRAKES.value: BrakeSubsystem(),
            Subsystem.COOLING.value: CoolingSubsystem(),
            Subsystem.BATTERY.value: BatterySubsystem(),
            Subsystem.TRANSMISSION.value: TransmissionSubsystem(),
            Subsystem.ELECTRICAL.value: ElectricalSubsystem(),
        }

    return _SUBSYSTEM_REGISTRY


def check_all_thresholds(state: VehicleState) -> List[Dict[str, Any]]:
    """
    Check all subsystem thresholds at once.

    Args:
        state: Current vehicle state

    Returns:
        Combined list of all threshold violations.
    """
    registry = get_subsystem_registry()
    all_violations = []

    for subsystem in registry.values():
        violations = subsystem.check_thresholds(state)
        all_violations.extend(violations)

    return all_violations


def get_subsystem_for_signal(signal_name: str) -> Optional[str]:
    """
    Find which subsystem a signal belongs to.

    Args:
        signal_name: Signal name (e.g., "temp", "rpm")

    Returns:
        Subsystem name or None.
    """
    registry = get_subsystem_registry()
    for name, subsystem in registry.items():
        if signal_name in subsystem.monitored_signals:
            return name
    return None