"""
============================================================================
AutoTwin AI - Scenario Engine
============================================================================
Orchestrates scenario execution by injecting signals into the
vehicle state at timed intervals.

The scenario engine:
  1. Loads a scenario definition
  2. Advances through steps based on elapsed time
  3. Injects signal values into the state manager
  4. Emits scenario progress events
  5. Handles start/stop/pause

Usage:
    engine = ScenarioEngine(event_bus, settings)
    await engine.start("engine_overheat")
    # ... scenario runs automatically ...
    await engine.stop()
============================================================================
"""

import asyncio
import time
from typing import Any, Dict, Optional

from loguru import logger

from app.core.constants import EventType
from app.core.event_bus import EventBus
from app.scenarios.scenario_definitions import ScenarioDefinition, ScenarioLibrary


# ============================================================================
# SCENARIO ENGINE
# ============================================================================


class ScenarioEngine:
    """
    Executes predefined scenarios by injecting signals over time.

    Runs as an async task, advancing through scenario steps
    at the configured tick rate.
    """

    def __init__(self, event_bus: EventBus, tick_interval_ms: int = 50):
        self._event_bus = event_bus
        self._library = ScenarioLibrary()
        self._tick_interval = tick_interval_ms / 1000.0

        # Active scenario state
        self._active_scenario: Optional[ScenarioDefinition] = None
        self._start_time: float = 0.0
        self._elapsed: float = 0.0
        self._running: bool = False
        self._paused: bool = False
        self._task: Optional[asyncio.Task] = None

        # Statistics
        self._scenarios_run: int = 0
        self._signals_injected: int = 0

    # ========================================================================
    # SCENARIO CONTROL
    # ========================================================================

    async def start(self, scenario_id: str) -> bool:
        """
        Start a scenario.

        Args:
            scenario_id: ID of the scenario to run

        Returns:
            True if scenario started successfully
        """
        if self._running:
            logger.warning(f"ScenarioEngine: scenario already active, stop it first")
            return False

        scenario = self._library.get(scenario_id)
        if not scenario:
            logger.error(f"ScenarioEngine: scenario '{scenario_id}' not found")
            return False

        self._active_scenario = scenario
        self._start_time = time.time()
        self._elapsed = 0.0
        self._running = True
        self._paused = False

        # Start execution task
        self._task = asyncio.create_task(self._execution_loop())

        # Emit start event
        await self._event_bus.publish(
            EventType.SCENARIO_STARTED,
            data=scenario.to_dict(),
            source="scenario_engine",
        )

        logger.info(f"ScenarioEngine: started '{scenario.name}' ({scenario.duration_s}s)")
        return True

    async def stop(self) -> None:
        """Stop the active scenario."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        scenario_name = self._active_scenario.name if self._active_scenario else "unknown"

        await self._event_bus.publish(
            EventType.SCENARIO_STOPPED,
            data={
                "scenario_id": self._active_scenario.scenario_id if self._active_scenario else "",
                "elapsed_s": self._elapsed,
                "completed": self._elapsed >= (self._active_scenario.duration_s if self._active_scenario else 0),
            },
            source="scenario_engine",
        )

        self._active_scenario = None
        self._scenarios_run += 1
        logger.info(f"ScenarioEngine: stopped '{scenario_name}' at {self._elapsed:.1f}s")

    async def pause(self) -> None:
        """Pause the active scenario."""
        self._paused = True

    async def resume(self) -> None:
        """Resume a paused scenario."""
        self._paused = False

    # ========================================================================
    # EXECUTION LOOP
    # ========================================================================

    async def _execution_loop(self) -> None:
        """Main scenario execution loop."""
        try:
            while self._running and self._active_scenario:
                if self._paused:
                    await asyncio.sleep(self._tick_interval)
                    continue

                self._elapsed = time.time() - self._start_time

                # Check if scenario complete
                if self._elapsed >= self._active_scenario.duration_s:
                    logger.info(f"ScenarioEngine: scenario completed naturally")
                    await self.stop()
                    return

                # Get current step
                step = self._active_scenario.get_step_at(self._elapsed)
                if step and step.signals:
                    # Emit scenario tick with signals to inject
                    await self._event_bus.publish(
                        EventType.SCENARIO_TICK,
                        data={
                            "signals": step.signals,
                            "elapsed_s": self._elapsed,
                            "progress": self._elapsed / self._active_scenario.duration_s,
                            "step_description": step.description,
                        },
                        source="scenario_engine",
                    )
                    self._signals_injected += len(step.signals)

                await asyncio.sleep(self._tick_interval)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"ScenarioEngine: execution error: {e}")

    # ========================================================================
    # QUERIES
    # ========================================================================

    def get_available_scenarios(self) -> list:
        """Get list of all available scenarios."""
        return [s.to_dict() for s in self._library.get_all()]

    def get_active_scenario(self) -> Optional[Dict[str, Any]]:
        """Get info about the currently active scenario."""
        if not self._active_scenario:
            return None
        return {
            **self._active_scenario.to_dict(),
            "elapsed_s": self._elapsed,
            "progress": self._elapsed / self._active_scenario.duration_s,
            "is_paused": self._paused,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> Dict[str, Any]:
        return {
            "scenarios_run": self._scenarios_run,
            "signals_injected": self._signals_injected,
            "is_running": self._running,
            "active_scenario": self._active_scenario.scenario_id if self._active_scenario else None,
        }