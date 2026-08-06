"""
============================================================================
AutoTwin AI - Scenarios Module
============================================================================
Predefined driving scenarios and CAN log replay:
  - ScenarioEngine: Orchestrates scenario execution
  - ScenarioDefinitions: Built-in scenario library
  - ReplayEngine: Plays back recorded CAN logs

Usage:
    engine = ScenarioEngine(state_manager, event_bus)
    await engine.start("engine_overheat")
    await engine.stop()
============================================================================
"""

from app.scenarios.scenario_engine import ScenarioEngine  # noqa: F401
from app.scenarios.scenario_definitions import (  # noqa: F401
    ScenarioDefinition,
    ScenarioStep,
    ScenarioLibrary,
)
from app.scenarios.replay_engine import ReplayEngine  # noqa: F401

__all__ = [
    "ScenarioEngine",
    "ScenarioDefinition",
    "ScenarioStep",
    "ScenarioLibrary",
    "ReplayEngine",
]