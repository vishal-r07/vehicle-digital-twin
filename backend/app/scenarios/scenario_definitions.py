"""
============================================================================
AutoTwin AI - Scenario Definitions
============================================================================
Predefined driving/fault scenarios for demonstration and testing.

Each scenario is a sequence of timed signal injections:
  - normal_driving: Typical city/highway driving
  - engine_overheat: Temperature rises to critical
  - battery_failure: Voltage drops progressively
  - abs_activation: Hard braking with ABS
  - door_open_driving: Door opens while moving
  - engine_stall: Engine dies at speed
  - fuel_leak: Fuel level drops rapidly

Format:
  Each scenario has steps:
    {time_s: 0, signals: {"speed": 0, "rpm": 800, ...}}
    {time_s: 5, signals: {"speed": 30, "rpm": 1500, ...}}
============================================================================
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class ScenarioStep:
    """A single step in a scenario (signal injection at a specific time)."""

    time_s: float  # Seconds from scenario start
    signals: Dict[str, Any] = field(default_factory=dict)
    duration_s: float = 1.0  # How long this step lasts
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_s": self.time_s,
            "signals": self.signals,
            "duration_s": self.duration_s,
            "description": self.description,
        }


@dataclass
class ScenarioDefinition:
    """Complete scenario definition."""

    scenario_id: str
    name: str
    description: str = ""
    category: str = "normal"  # normal, fault, stress, demo
    duration_s: float = 60.0
    steps: List[ScenarioStep] = field(default_factory=list)
    is_builtin: bool = True

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def get_step_at(self, time_s: float) -> Optional[ScenarioStep]:
        """Get the active step at a given time."""
        for step in reversed(self.steps):
            if time_s >= step.time_s:
                return step
        return self.steps[0] if self.steps else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "duration_s": self.duration_s,
            "step_count": self.step_count,
            "is_builtin": self.is_builtin,
        }


# ============================================================================
# SCENARIO LIBRARY
# ============================================================================


class ScenarioLibrary:
    """
    Built-in scenario definitions.

    Provides a collection of predefined scenarios for
    demonstration, testing, and training.
    """

    def __init__(self):
        self._scenarios: Dict[str, ScenarioDefinition] = {}
        self._load_builtin_scenarios()

    def _load_builtin_scenarios(self) -> None:
        """Load all built-in scenarios."""
        self._scenarios["normal_driving"] = self._create_normal_driving()
        self._scenarios["city_traffic"] = self._create_city_traffic()
        self._scenarios["highway_cruise"] = self._create_highway_cruise()
        self._scenarios["engine_overheat"] = self._create_engine_overheat()
        self._scenarios["battery_failure"] = self._create_battery_failure()
        self._scenarios["abs_activation"] = self._create_abs_activation()
        self._scenarios["door_open_driving"] = self._create_door_open()
        self._scenarios["engine_stall"] = self._create_engine_stall()
        self._scenarios["fuel_leak"] = self._create_fuel_leak()

        logger.info(f"ScenarioLibrary: loaded {len(self._scenarios)} built-in scenarios")

    def get(self, scenario_id: str) -> Optional[ScenarioDefinition]:
        return self._scenarios.get(scenario_id)

    def get_all(self) -> List[ScenarioDefinition]:
        return list(self._scenarios.values())

    def get_by_category(self, category: str) -> List[ScenarioDefinition]:
        return [s for s in self._scenarios.values() if s.category == category]

    # ========================================================================
    # BUILT-IN SCENARIO DEFINITIONS
    # ========================================================================

    def _create_normal_driving(self) -> ScenarioDefinition:
        return ScenarioDefinition(
            scenario_id="normal_driving",
            name="Normal Driving",
            description="Typical driving cycle with acceleration, cruising, and braking",
            category="normal",
            duration_s=120.0,
            steps=[
                ScenarioStep(0, {"speed": 0, "rpm": 800, "gear": "P", "fuel": 85, "temp": 60, "battery": 12.6}),
                ScenarioStep(5, {"speed": 0, "rpm": 900, "gear": "D", "accelerator": 0}),
                ScenarioStep(10, {"speed": 20, "rpm": 1500, "accelerator": 30, "temp": 70}),
                ScenarioStep(20, {"speed": 40, "rpm": 2000, "accelerator": 25, "temp": 80}),
                ScenarioStep(35, {"speed": 60, "rpm": 2200, "accelerator": 20, "temp": 88}),
                ScenarioStep(50, {"speed": 60, "rpm": 2100, "accelerator": 15, "temp": 90, "battery": 13.8}),
                ScenarioStep(70, {"speed": 50, "rpm": 1800, "brake": 1, "accelerator": 0}),
                ScenarioStep(80, {"speed": 30, "rpm": 1200, "brake": 0, "accelerator": 10}),
                ScenarioStep(90, {"speed": 45, "rpm": 1800, "accelerator": 20, "steering": 15}),
                ScenarioStep(100, {"speed": 40, "rpm": 1600, "steering": -10, "indicator": 1}),
                ScenarioStep(110, {"speed": 20, "rpm": 1000, "brake": 1, "indicator": 0}),
                ScenarioStep(115, {"speed": 0, "rpm": 800, "gear": "P", "brake": 0}),
            ],
        )

    def _create_city_traffic(self) -> ScenarioDefinition:
        return ScenarioDefinition(
            scenario_id="city_traffic",
            name="City Traffic",
            description="Stop-and-go city driving with frequent braking",
            category="normal",
            duration_s=90.0,
            steps=[
                ScenarioStep(0, {"speed": 0, "rpm": 800, "gear": "D", "temp": 85}),
                ScenarioStep(5, {"speed": 15, "rpm": 1200, "accelerator": 20}),
                ScenarioStep(15, {"speed": 25, "rpm": 1500, "accelerator": 15}),
                ScenarioStep(20, {"speed": 0, "rpm": 900, "brake": 1, "accelerator": 0}),
                ScenarioStep(30, {"speed": 0, "rpm": 850, "brake": 0}),
                ScenarioStep(35, {"speed": 20, "rpm": 1400, "accelerator": 25}),
                ScenarioStep(45, {"speed": 35, "rpm": 1800, "accelerator": 15}),
                ScenarioStep(50, {"speed": 10, "rpm": 1000, "brake": 1}),
                ScenarioStep(55, {"speed": 0, "rpm": 850, "brake": 0}),
                ScenarioStep(65, {"speed": 30, "rpm": 1600, "accelerator": 20, "steering": 30}),
                ScenarioStep(75, {"speed": 20, "rpm": 1200, "steering": -20}),
                ScenarioStep(85, {"speed": 0, "rpm": 800, "brake": 1}),
            ],
        )

    def _create_highway_cruise(self) -> ScenarioDefinition:
        return ScenarioDefinition(
            scenario_id="highway_cruise",
            name="Highway Cruise",
            description="Steady high-speed highway driving",
            category="normal",
            duration_s=60.0,
            steps=[
                ScenarioStep(0, {"speed": 80, "rpm": 2000, "gear": "D", "temp": 90, "fuel": 70}),
                ScenarioStep(10, {"speed": 100, "rpm": 2200, "accelerator": 25}),
                ScenarioStep(20, {"speed": 120, "rpm": 2500, "accelerator": 30}),
                ScenarioStep(30, {"speed": 120, "rpm": 2400, "accelerator": 25, "battery": 14.0}),
                ScenarioStep(40, {"speed": 110, "rpm": 2200, "accelerator": 20, "steering": 3}),
                ScenarioStep(50, {"speed": 120, "rpm": 2500, "accelerator": 28}),
            ],
        )

    def _create_engine_overheat(self) -> ScenarioDefinition:
        return ScenarioDefinition(
            scenario_id="engine_overheat",
            name="Engine Overheat",
            description="Coolant temperature rises to critical level",
            category="fault",
            duration_s=60.0,
            steps=[
                ScenarioStep(0, {"speed": 60, "rpm": 2500, "temp": 90, "gear": "D"}),
                ScenarioStep(5, {"temp": 95, "speed": 65, "rpm": 2800}),
                ScenarioStep(10, {"temp": 100, "speed": 70, "rpm": 3000, "engine_load": 60}),
                ScenarioStep(15, {"temp": 105, "speed": 70, "rpm": 3200, "engine_load": 70}),
                ScenarioStep(20, {"temp": 108, "speed": 65, "rpm": 3000}),
                ScenarioStep(25, {"temp": 112, "speed": 60, "rpm": 2800}),
                ScenarioStep(30, {"temp": 115, "speed": 50, "rpm": 2500, "accelerator": 10}),
                ScenarioStep(35, {"temp": 118, "speed": 40, "rpm": 2000}),
                ScenarioStep(40, {"temp": 120, "speed": 30, "rpm": 1500}),
                ScenarioStep(45, {"temp": 122, "speed": 20, "rpm": 1200}),
                ScenarioStep(50, {"temp": 118, "speed": 0, "rpm": 900, "gear": "P"}),
                ScenarioStep(55, {"temp": 110, "speed": 0, "rpm": 800}),
            ],
        )

    def _create_battery_failure(self) -> ScenarioDefinition:
        return ScenarioDefinition(
            scenario_id="battery_failure",
            name="Battery Failure",
            description="Battery voltage drops progressively",
            category="fault",
            duration_s=60.0,
            steps=[
                ScenarioStep(0, {"speed": 50, "rpm": 2000, "battery": 12.6, "gear": "D"}),
                ScenarioStep(10, {"battery": 12.2, "speed": 50}),
                ScenarioStep(20, {"battery": 11.8, "speed": 45}),
                ScenarioStep(30, {"battery": 11.4, "speed": 40, "headlight": 1}),
                ScenarioStep(40, {"battery": 11.0, "speed": 35}),
                ScenarioStep(50, {"battery": 10.5, "speed": 30, "rpm": 1500}),
                ScenarioStep(55, {"battery": 10.2, "speed": 20, "rpm": 1000}),
            ],
        )

    def _create_abs_activation(self) -> ScenarioDefinition:
        return ScenarioDefinition(
            scenario_id="abs_activation",
            name="ABS Activation",
            description="Hard braking triggers ABS intervention",
            category="fault",
            duration_s=30.0,
            steps=[
                ScenarioStep(0, {"speed": 80, "rpm": 2500, "gear": "D", "temp": 90}),
                ScenarioStep(5, {"speed": 80, "rpm": 2400, "accelerator": 20}),
                ScenarioStep(8, {"speed": 75, "brake": 1, "accelerator": 0, "brake_pressure": 80}),
                ScenarioStep(10, {"speed": 60, "brake": 1, "abs": 1, "brake_pressure": 120}),
                ScenarioStep(12, {"speed": 45, "brake": 1, "abs": 1, "brake_pressure": 100}),
                ScenarioStep(15, {"speed": 30, "brake": 1, "abs": 0, "brake_pressure": 60}),
                ScenarioStep(20, {"speed": 10, "brake": 1, "brake_pressure": 30}),
                ScenarioStep(25, {"speed": 0, "brake": 0, "rpm": 900}),
            ],
        )

    def _create_door_open(self) -> ScenarioDefinition:
        return ScenarioDefinition(
            scenario_id="door_open_driving",
            name="Door Open While Driving",
            description="Driver door opens while vehicle is moving",
            category="fault",
            duration_s=30.0,
            steps=[
                ScenarioStep(0, {"speed": 40, "rpm": 1800, "gear": "D", "door": "Closed"}),
                ScenarioStep(5, {"speed": 45, "rpm": 2000}),
                ScenarioStep(10, {"door": "FL", "speed": 45}),
                ScenarioStep(15, {"speed": 40, "rpm": 1800, "door": "FL"}),
                ScenarioStep(20, {"speed": 30, "brake": 1, "door": "FL"}),
                ScenarioStep(25, {"speed": 10, "door": "FL"}),
                ScenarioStep(28, {"speed": 0, "door": "Closed", "gear": "P"}),
            ],
        )

    def _create_engine_stall(self) -> ScenarioDefinition:
        return ScenarioDefinition(
            scenario_id="engine_stall",
            name="Engine Stall",
            description="Engine stalls while driving",
            category="fault",
            duration_s=30.0,
            steps=[
                ScenarioStep(0, {"speed": 50, "rpm": 2000, "gear": "D", "temp": 88}),
                ScenarioStep(5, {"speed": 50, "rpm": 1800}),
                ScenarioStep(8, {"speed": 48, "rpm": 1200}),
                ScenarioStep(10, {"speed": 45, "rpm": 600}),
                ScenarioStep(12, {"speed": 40, "rpm": 0, "engine_load": 0}),
                ScenarioStep(15, {"speed": 35, "rpm": 0, "battery": 12.4}),
                ScenarioStep(20, {"speed": 25, "rpm": 0, "brake": 1}),
                ScenarioStep(25, {"speed": 10, "rpm": 0, "brake": 1}),
                ScenarioStep(28, {"speed": 0, "rpm": 0, "gear": "N"}),
            ],
        )

    def _create_fuel_leak(self) -> ScenarioDefinition:
        return ScenarioDefinition(
            scenario_id="fuel_leak",
            name="Fuel Leak",
            description="Fuel level drops rapidly due to leak",
            category="fault",
            duration_s=60.0,
            steps=[
                ScenarioStep(0, {"speed": 60, "rpm": 2200, "fuel": 50, "gear": "D"}),
                ScenarioStep(10, {"fuel": 42, "speed": 60}),
                ScenarioStep(20, {"fuel": 34, "speed": 55}),
                ScenarioStep(30, {"fuel": 25, "speed": 50}),
                ScenarioStep(40, {"fuel": 15, "speed": 45}),
                ScenarioStep(50, {"fuel": 8, "speed": 40}),
                ScenarioStep(55, {"fuel": 3, "speed": 35}),
            ],
        )