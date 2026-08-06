"""
============================================================================
AutoTwin AI - Scenario Service
============================================================================
Orchestrates scenario execution and CAN log replay.

Coordinates:
  - ScenarioEngine (signal injection over time)
  - ReplayEngine (log playback)
  - StateManager (state updates)
  - EventBus (event coordination)

Only one of scenario/replay can be active at a time.

Usage:
    service = ScenarioService(event_bus, state_manager)
    await service.start_scenario("engine_overheat")
    await service.stop_scenario()
    await service.start_replay("log_file_id")
============================================================================
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.constants import EventType
from app.core.event_bus import Event, EventBus
from app.scenarios.scenario_engine import ScenarioEngine
from app.scenarios.scenario_definitions import ScenarioLibrary
from app.scenarios.replay_engine import ReplayEngine


# ============================================================================
# SCENARIO SERVICE
# ============================================================================


class ScenarioService:
    """
    Orchestrates scenario execution and replay.

    Ensures mutual exclusion between scenario and replay modes.
    Bridges scenario signal injections to the vehicle state manager.
    """

    def __init__(self, event_bus: EventBus, state_manager=None, settings=None):
        self._event_bus = event_bus
        self._state_manager = state_manager
        self._settings = settings

        # Engines
        self._scenario_engine = ScenarioEngine(event_bus)
        self._replay_engine = ReplayEngine(event_bus)

        # Mode tracking
        self._active_mode: Optional[str] = None  # "scenario", "replay", or None

        # Subscription for scenario ticks
        self._tick_subscription = None

        logger.info("ScenarioService: initialized")

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    async def start(self) -> None:
        """Start the scenario service (subscribe to events)."""
        self._tick_subscription = self._event_bus.subscribe(
            EventType.SCENARIO_TICK,
            self._on_scenario_tick,
            priority=5,
        )
        logger.info("ScenarioService: started")

    async def stop(self) -> None:
        """Stop the scenario service."""
        if self._tick_subscription:
            self._event_bus.unsubscribe(self._tick_subscription)

        await self.stop_scenario()
        await self.stop_replay()
        logger.info("ScenarioService: stopped")

    # ========================================================================
    # SCENARIO CONTROL
    # ========================================================================

    async def start_scenario(self, scenario_id: str) -> bool:
        """
        Start a scenario.

        Args:
            scenario_id: Scenario identifier

        Returns:
            True if started successfully
        """
        # Check mutual exclusion
        if self._active_mode == "replay":
            logger.warning("ScenarioService: stop replay before starting scenario")
            await self.stop_replay()

        if self._active_mode == "scenario":
            logger.warning("ScenarioService: scenario already active")
            return False

        success = await self._scenario_engine.start(scenario_id)
        if success:
            self._active_mode = "scenario"
            logger.info(f"ScenarioService: scenario '{scenario_id}' started")

        return success

    async def stop_scenario(self) -> None:
        """Stop the active scenario."""
        if self._active_mode == "scenario":
            await self._scenario_engine.stop()
            self._active_mode = None
            logger.info("ScenarioService: scenario stopped")

    async def pause_scenario(self) -> None:
        """Pause the active scenario."""
        await self._scenario_engine.pause()

    async def resume_scenario(self) -> None:
        """Resume a paused scenario."""
        await self._scenario_engine.resume()

    def get_available_scenarios(self) -> List[Dict[str, Any]]:
        """Get list of all available scenarios."""
        return self._scenario_engine.get_available_scenarios()

    def get_active_scenario(self) -> Optional[Dict[str, Any]]:
        """Get info about the active scenario."""
        if self._active_mode != "scenario":
            return None
        return self._scenario_engine.get_active_scenario()

    # ========================================================================
    # REPLAY CONTROL
    # ========================================================================

    async def start_replay(self, log_path: str, speed: float = 1.0) -> bool:
        """
        Start replaying a CAN log.

        Args:
            log_path: Path to the log file
            speed: Playback speed multiplier

        Returns:
            True if started successfully
        """
        # Check mutual exclusion
        if self._active_mode == "scenario":
            logger.warning("ScenarioService: stop scenario before starting replay")
            await self.stop_scenario()

        if self._active_mode == "replay":
            await self.stop_replay()

        # Load and play
        loaded = await self._replay_engine.load(log_path)
        if not loaded:
            return False

        await self._replay_engine.play(speed=speed)
        self._active_mode = "replay"
        logger.info(f"ScenarioService: replay started (speed={speed}x)")
        return True

    async def stop_replay(self) -> None:
        """Stop the active replay."""
        if self._active_mode == "replay":
            await self._replay_engine.stop()
            self._active_mode = None
            logger.info("ScenarioService: replay stopped")

    async def pause_replay(self) -> None:
        await self._replay_engine.pause()

    async def resume_replay(self) -> None:
        await self._replay_engine.resume()

    async def seek_replay(self, position_s: float) -> None:
        await self._replay_engine.seek(position_s)

    def set_replay_speed(self, speed: float) -> None:
        self._replay_engine.set_speed(speed)

    def get_replay_status(self) -> Dict[str, Any]:
        return self._replay_engine.get_stats()

    # ========================================================================
    # SCENARIO TICK HANDLER
    # ========================================================================

    async def _on_scenario_tick(self, event: Event) -> None:
        """
        Handle scenario tick event.

        Injects scenario signals into the vehicle state manager.
        """
        data = event.data
        if not data:
            return

        signals = data.get("signals", {})
        if not signals:
            return

        # Inject into state manager
        if self._state_manager:
            await self._state_manager.update_signals_batch(
                signals, source="scenario"
            )

    # ========================================================================
    # PROPERTIES & STATS
    # ========================================================================

    @property
    def active_mode(self) -> Optional[str]:
        """Current active mode: 'scenario', 'replay', or None."""
        return self._active_mode

    @property
    def is_active(self) -> bool:
        """Whether any scenario/replay is active."""
        return self._active_mode is not None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active_mode": self._active_mode,
            "scenario_stats": self._scenario_engine.get_stats(),
            "replay_stats": self._replay_engine.get_stats(),
        }