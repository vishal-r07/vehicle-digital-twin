"""
============================================================================
AutoTwin AI - Broadcast Service
============================================================================
The main real-time broadcast loop. Reads vehicle state and pushes
updates to all connected WebSocket clients at 20 Hz.

Responsibilities:
  - Run the 20 Hz broadcast loop as an async background task
  - Read current state from VehicleStateManager
  - Format and send via WebSocketManager
  - Coordinate periodic health updates
  - Handle serial data → state updates
  - Bridge hardware reader to state manager

This is the HEARTBEAT of the real-time system.

Data Flow:
  SerialReader → frame queue → BroadcastService → StateManager → WS Clients

Usage:
    service = BroadcastService(state_manager, ws_manager, event_bus)
    await service.start()   # Starts background tasks
    await service.stop()    # Graceful shutdown
============================================================================
"""

import asyncio
import time
from typing import Any, Dict, Optional

from loguru import logger

from app.config import BroadcastSettings
from app.core.constants import EventType, DataSource
from app.core.event_bus import Event, EventBus
from app.core.state_manager import VehicleStateManager
from app.can.frame_parser import CANFrameParser
from app.vehicle.state_updater import StateUpdater
from app.vehicle.vehicle_state import VehicleState


# ============================================================================
# BROADCAST SERVICE
# ============================================================================


class BroadcastService:
    """
    Main real-time broadcast orchestrator.

    Runs background tasks:
      1. Serial frame consumer (reads from hardware)
      2. State broadcast loop (20 Hz to WebSocket)
      3. Staleness checker (periodic)

    Coordinates the complete data pipeline from hardware to frontend.
    """

    def __init__(
        self,
        state_manager: VehicleStateManager,
        ws_manager,
        event_bus: EventBus,
        settings: BroadcastSettings,
        serial_reader=None,
        can_parser: Optional[CANFrameParser] = None,
    ):
        self._state_manager = state_manager
        self._ws_manager = ws_manager
        self._event_bus = event_bus
        self._settings = settings
        self._serial_reader = serial_reader
        self._can_parser = can_parser or CANFrameParser()
        self._state_updater = StateUpdater()

        # Vehicle state object (for state updater)
        self._vehicle_state = VehicleState()

        # Background tasks
        self._broadcast_task: Optional[asyncio.Task] = None
        self._consumer_task: Optional[asyncio.Task] = None
        self._staleness_task: Optional[asyncio.Task] = None
        self._running: bool = False

        # Timing
        self._broadcast_interval = settings.interval_ms / 1000.0
        self._last_broadcast: float = 0.0
        self._broadcast_count: int = 0

        # Subscriptions
        self._subscriptions = []

        logger.info(
            f"BroadcastService: initialized "
            f"(interval={settings.interval_ms}ms, "
            f"rate={1000 // settings.interval_ms}Hz)"
        )

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    async def start(self) -> None:
        """Start all broadcast background tasks."""
        self._running = True

        # Subscribe to relevant events
        self._subscriptions.append(
            self._event_bus.subscribe(
                EventType.SCENARIO_TICK,
                self._on_external_state_update,
                priority=5,
            )
        )
        self._subscriptions.append(
            self._event_bus.subscribe(
                EventType.STATE_UPDATED,
                self._on_external_state_update,
                priority=5,
            )
        )

        # Start frame consumer (reads from serial/simulator)
        if self._serial_reader:
            self._consumer_task = asyncio.create_task(
                self._frame_consumer_loop(),
                name="frame-consumer",
            )

        # Start broadcast loop
        self._broadcast_task = asyncio.create_task(
            self._broadcast_loop(),
            name="broadcast-loop",
        )

        # Start staleness checker
        self._staleness_task = asyncio.create_task(
            self._staleness_checker_loop(),
            name="staleness-checker",
        )

        logger.info("BroadcastService: all tasks started")

    async def stop(self) -> None:
        """Stop all broadcast tasks gracefully."""
        self._running = False

        # Unsubscribe events
        for sub in self._subscriptions:
            self._event_bus.unsubscribe(sub)
        self._subscriptions.clear()

        # Cancel tasks
        tasks = [self._broadcast_task, self._consumer_task, self._staleness_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info(
            f"BroadcastService: stopped "
            f"({self._broadcast_count} broadcasts sent)"
        )

    # ========================================================================
    # FRAME CONSUMER LOOP (Hardware → State)
    # ========================================================================

    async def _frame_consumer_loop(self) -> None:
        """
        Background task: consume frames from serial reader and update state.

        Reads RawFrames from the serial reader queue, decodes them,
        and applies to the vehicle state manager.
        """
        logger.info("BroadcastService: frame consumer started")

        while self._running:
            try:
                # Read frame from serial reader
                frame = await self._serial_reader.read(timeout=0.05)

                if frame is None:
                    continue

                # Decode frame
                if frame.is_parsed_frame:
                    # Pre-parsed serial frame (from STM32)
                    decoded = self._can_parser.decode_serial_frame(frame.signals)
                    state_update = self._can_parser.to_state_update(decoded)

                    # Apply to state manager
                    if state_update:
                        await self._state_manager.update_signals_batch(
                            state_update, source="serial"
                        )

                        # Also apply to VehicleState object (for state_updater)
                        self._state_updater.apply(self._vehicle_state, state_update)

                elif frame.is_can_frame:
                    # Raw CAN frame (from USB-CAN adapter)
                    decoded = self._can_parser.decode_can_frame(
                        frame.can_id, frame.data, frame.dlc
                    )
                    state_update = self._can_parser.to_state_update(decoded)

                    if state_update:
                        await self._state_manager.update_signals_batch(
                            state_update, source="can"
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"BroadcastService: consumer error: {e}")
                await asyncio.sleep(0.1)

    # ========================================================================
    # BROADCAST LOOP (State → WebSocket)
    # ========================================================================

    async def _broadcast_loop(self) -> None:
        """
        Background task: broadcast vehicle state to WebSocket clients.

        Runs at configured interval (default 50ms = 20 Hz).
        Sends compact state to all connected clients.
        """
        logger.info(
            f"BroadcastService: broadcast loop started "
            f"({1.0 / self._broadcast_interval:.0f} Hz)"
        )

        while self._running:
            try:
                now = time.time()

                # Rate limiting
                elapsed = now - self._last_broadcast
                if elapsed < self._broadcast_interval:
                    await asyncio.sleep(self._broadcast_interval - elapsed)
                    continue

                self._last_broadcast = now

                # Check if we have clients
                if self._ws_manager.client_count == 0:
                    continue

                # Get current state
                state_dict = self._state_manager.get_state_dict()

                # Add metadata
                state_dict["timestamp"] = now
                state_dict["seq"] = self._broadcast_count

                # Broadcast to all clients
                await self._ws_manager.broadcast_vehicle_state(state_dict)
                self._broadcast_count += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"BroadcastService: broadcast error: {e}")
                await asyncio.sleep(0.1)

    # ========================================================================
    # STALENESS CHECKER
    # ========================================================================

    async def _staleness_checker_loop(self) -> None:
        """
        Background task: periodically check for stale signals.

        Emits SIGNAL_STALE events if signals haven't updated
        within their expected period.
        """
        check_interval = 0.5  # Check every 500ms

        while self._running:
            try:
                await asyncio.sleep(check_interval)
                await self._state_manager.check_staleness()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"BroadcastService: staleness check error: {e}")

    # ========================================================================
    # EXTERNAL STATE UPDATES (Scenario/Replay)
    # ========================================================================

    async def _on_external_state_update(self, event: Event) -> None:
        """
        Handle state updates from scenario engine or replay engine.

        These bypass the serial reader and inject directly.
        """
        data = event.data
        if not data:
            return

        # Extract signals
        signals = data.get("signals") or data.get("changed_signals", {})
        if not signals:
            return

        source = data.get("source", "external")

        # Apply to state manager
        await self._state_manager.update_signals_batch(signals, source=source)

        # Apply to local VehicleState
        self._state_updater.apply(self._vehicle_state, signals)

    # ========================================================================
    # MANUAL STATE INJECTION (for API/testing)
    # ========================================================================

    async def inject_signals(self, signals: Dict[str, Any], source: str = "api") -> int:
        """
        Manually inject signals into the state.

        Used by API endpoints for testing or manual override.

        Args:
            signals: Signal dictionary to inject
            source: Source identifier

        Returns:
            Number of signals that changed
        """
        changes = await self._state_manager.update_signals_batch(signals, source=source)
        self._state_updater.apply(self._vehicle_state, signals)
        return changes

    # ========================================================================
    # PROPERTIES & STATISTICS
    # ========================================================================

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def broadcast_count(self) -> int:
        return self._broadcast_count

    @property
    def broadcast_rate(self) -> float:
        """Actual broadcast rate (Hz)."""
        if self._broadcast_count < 2:
            return 0.0
        # Approximate based on recent activity
        return 1.0 / self._broadcast_interval

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "broadcast_count": self._broadcast_count,
            "broadcast_interval_ms": self._settings.interval_ms,
            "broadcast_rate_hz": round(1000 / self._settings.interval_ms, 1),
            "connected_clients": self._ws_manager.client_count,
            "state_stats": self._state_manager.get_stats(),
            "vehicle_state": {
                "speed": self._vehicle_state.body.speed,
                "rpm": self._vehicle_state.engine.rpm,
                "can_active": self._vehicle_state.can_active,
            },
        }