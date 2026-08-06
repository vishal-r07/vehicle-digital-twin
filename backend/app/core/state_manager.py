"""
============================================================================
AutoTwin AI - Vehicle State Manager
============================================================================
Central state store — the single source of truth for all vehicle signals.

Responsibilities:
  1. Store current vehicle state (all signals)
  2. Accept signal updates from CAN parser / scenario / replay
  3. Detect changes and emit events
  4. Track signal staleness
  5. Maintain state history (ring buffer for replay/correlation)
  6. Calculate rate-of-change for derivative-based diagnostics
  7. Provide thread-safe access

Design Pattern:
  Observable State Store with Event Emission

Data Flow:
  CAN Parser → state_manager.update_signal("speed", 58.0)
             → StateChangedEvent emitted
             → Fault Engine evaluates rules
             → WebSocket broadcasts to clients
             → 3D model updates

Usage:
    state_mgr = VehicleStateManager(event_bus)

    # Update a signal
    await state_mgr.update_signal("speed", 58.0, source="can_parser")

    # Get full state
    state = state_mgr.get_state_dict()

    # Get specific signal
    speed = state_mgr.get_signal("speed")
============================================================================
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from loguru import logger

from app.core.constants import EventType, DefaultThresholds, BufferSize
from app.core.event_bus import Event, EventBus


# ============================================================================
# SIGNAL VALUE DATA STRUCTURE
# ============================================================================


@dataclass
class SignalValue:
    """
    Represents a single signal with metadata.

    Tracks current value, previous value, timestamps, and rate of change.
    """

    name: str
    value: Any = None
    previous_value: Any = None
    unit: str = ""
    timestamp: float = field(default_factory=time.time)
    previous_timestamp: float = 0.0
    update_count: int = 0
    is_stale: bool = False
    expected_period_ms: float = 0.0  # 0 = no staleness check

    @property
    def age_ms(self) -> float:
        """Milliseconds since last update."""
        return (time.time() - self.timestamp) * 1000

    @property
    def rate_of_change(self) -> float:
        """Rate of change per second (0 if cannot calculate)."""
        if self.previous_timestamp == 0 or self.timestamp == self.previous_timestamp:
            return 0.0
        dt = self.timestamp - self.previous_timestamp
        if dt <= 0:
            return 0.0
        try:
            return (float(self.value) - float(self.previous_value)) / dt
        except (TypeError, ValueError):
            return 0.0

    @property
    def delta(self) -> float:
        """Change since last update."""
        try:
            return float(self.value) - float(self.previous_value)
        except (TypeError, ValueError):
            return 0.0

    def update(self, new_value: Any) -> bool:
        """
        Update signal value.

        Returns:
            True if value actually changed.
        """
        changed = new_value != self.value
        self.previous_value = self.value
        self.previous_timestamp = self.timestamp
        self.value = new_value
        self.timestamp = time.time()
        self.update_count += 1
        self.is_stale = False
        return changed


# ============================================================================
# STATE SNAPSHOT
# ============================================================================


@dataclass
class StateSnapshot:
    """Immutable snapshot of vehicle state at a point in time."""

    sequence: int
    timestamp: float
    signals: Dict[str, Any]
    frame_count: int
    can_active: bool
    active_faults: List[str] = field(default_factory=list)


# ============================================================================
# VEHICLE STATE MANAGER
# ============================================================================


class VehicleStateManager:
    """
    Central vehicle state store.

    This is the SINGLE SOURCE OF TRUTH for all vehicle signals.
    All modules read from here. Only the CAN parser, scenario engine,
    and replay engine write to here.

    Thread Safety:
        Uses asyncio lock for concurrent access protection.
        All public methods are async.
    """

    def __init__(self, event_bus: EventBus, history_size: int = BufferSize.STATE_HISTORY):
        """
        Initialize the state manager.

        Args:
            event_bus: Event bus for emitting state change events.
            history_size: Number of state snapshots to retain.
        """
        self._event_bus = event_bus
        self._signals: Dict[str, SignalValue] = {}
        self._history: deque = deque(maxlen=history_size)
        self._sequence: int = 0
        self._frame_count: int = 0
        self._can_active: bool = False
        self._session_start: float = time.time()
        self._last_update: float = 0.0
        self._lock = asyncio.Lock()

        # Subscribers for direct state change notification (faster than event bus)
        self._change_callbacks: List[Callable[[str, Any, Any], None]] = []

        # Signal metadata (units, expected frequencies)
        self._signal_metadata: Dict[str, Dict[str, Any]] = {}

        # Initialize default signals
        self._initialize_signals()

        logger.info(f"VehicleStateManager initialized ({len(self._signals)} signals)")

    # ========================================================================
    # INITIALIZATION
    # ========================================================================

    def _initialize_signals(self) -> None:
        """Initialize all Phase 1 signals with default values."""
        defaults = {
            "speed": (0.0, "km/h", 50),
            "rpm": (0, "rpm", 20),
            "fuel": (100.0, "%", 1000),
            "temp": (25, "°C", 500),
            "battery": (12.6, "V", 1000),
            "steering": (0.0, "deg", 50),
            "brake": (0, "", 100),
            "accelerator": (0.0, "%", 50),
            "gear": ("P", "", 2000),
            "door": ("Closed", "", 3000),
            "indicator": (0, "", 500),
            "headlight": (0, "", 1000),
            "engine_load": (0.0, "%", 100),
            "ambient_temp": (25, "°C", 5000),
            "odometer": (0.0, "km", 5000),
            "wheel_fl": (0.0, "km/h", 50),
            "wheel_fr": (0.0, "km/h", 50),
            "wheel_rl": (0.0, "km/h", 50),
            "wheel_rr": (0.0, "km/h", 50),
            "abs": (0, "", 100),
            "brake_pressure": (0.0, "bar", 100),
        }

        for name, (default_val, unit, period_ms) in defaults.items():
            self._signals[name] = SignalValue(
                name=name,
                value=default_val,
                unit=unit,
                expected_period_ms=period_ms,
            )
            self._signal_metadata[name] = {
                "unit": unit,
                "expected_period_ms": period_ms,
            }

    # ========================================================================
    # STATE UPDATES
    # ========================================================================

    async def update_signal(
        self,
        name: str,
        value: Any,
        source: str = "can_parser",
        emit_event: bool = True,
    ) -> bool:
        """
        Update a single signal value.

        Args:
            name: Signal name (must match SignalName enum)
            value: New value
            source: Source identifier
            emit_event: Whether to emit StateChanged event

        Returns:
            True if value changed, False if same.
        """
        async with self._lock:
            if name not in self._signals:
                # Auto-create unknown signals (for future extensibility)
                self._signals[name] = SignalValue(name=name)
                logger.debug(f"VSM: auto-created signal '{name}'")

            signal = self._signals[name]
            changed = signal.update(value)

            if changed:
                self._last_update = time.time()
                self._frame_count += 1

                # Notify direct callbacks
                for callback in self._change_callbacks:
                    try:
                        callback(name, value, signal.previous_value)
                    except Exception as e:
                        logger.error(f"VSM: change callback error: {e}")

                # Emit event
                if emit_event:
                    await self._event_bus.publish_nowait(
                        EventType.STATE_CHANGED,
                        data={
                            "signal": name,
                            "value": value,
                            "previous": signal.previous_value,
                            "delta": signal.delta,
                            "rate_of_change": signal.rate_of_change,
                            "source": source,
                        },
                        source="state_manager",
                    )

            return changed

    async def update_signals_batch(
        self,
        updates: Dict[str, Any],
        source: str = "can_parser",
        emit_single_event: bool = True,
    ) -> int:
        """
        Update multiple signals at once (more efficient than individual updates).

        Args:
            updates: Dictionary of {signal_name: new_value}
            source: Source identifier
            emit_single_event: Emit one event for all changes (vs per-signal)

        Returns:
            Number of signals that actually changed.
        """
        changed_signals = {}

        async with self._lock:
            for name, value in updates.items():
                if name not in self._signals:
                    self._signals[name] = SignalValue(name=name)

                signal = self._signals[name]
                if signal.update(value):
                    changed_signals[name] = {
                        "value": value,
                        "previous": signal.previous_value,
                        "delta": signal.delta,
                    }

            if changed_signals:
                self._last_update = time.time()
                self._frame_count += 1

        # Emit event outside lock
        if changed_signals and emit_single_event:
            await self._event_bus.publish_nowait(
                EventType.STATE_UPDATED,
                data={
                    "changed_signals": changed_signals,
                    "change_count": len(changed_signals),
                    "source": source,
                    "frame_count": self._frame_count,
                },
                source="state_manager",
            )

        return len(changed_signals)

    # ========================================================================
    # STATE QUERIES
    # ========================================================================

    def get_signal(self, name: str) -> Any:
        """Get current value of a signal."""
        signal = self._signals.get(name)
        return signal.value if signal else None

    def get_signal_info(self, name: str) -> Optional[SignalValue]:
        """Get full SignalValue object with metadata."""
        return self._signals.get(name)

    def get_state_dict(self) -> Dict[str, Any]:
        """
        Get complete state as a flat dictionary.
        Suitable for WebSocket broadcast and API responses.
        """
        return {name: sig.value for name, sig in self._signals.items()}

    def get_state_with_metadata(self) -> Dict[str, Any]:
        """Get state with additional metadata for frontend."""
        state = {}
        for name, sig in self._signals.items():
            state[name] = {
                "value": sig.value,
                "unit": sig.unit,
                "is_stale": sig.is_stale,
                "age_ms": round(sig.age_ms, 1),
                "rate_of_change": round(sig.rate_of_change, 3),
                "update_count": sig.update_count,
            }
        return state

    def get_subset(self, signal_names: List[str]) -> Dict[str, Any]:
        """Get only specific signals."""
        return {
            name: self._signals[name].value
            for name in signal_names
            if name in self._signals
        }

    def get_all_signal_names(self) -> List[str]:
        """Get list of all registered signal names."""
        return list(self._signals.keys())

    # ========================================================================
    # STATE HISTORY & SNAPSHOTS
    # ========================================================================

    def take_snapshot(self) -> StateSnapshot:
        """Create an immutable snapshot of current state."""
        self._sequence += 1
        snapshot = StateSnapshot(
            sequence=self._sequence,
            timestamp=time.time(),
            signals=self.get_state_dict(),
            frame_count=self._frame_count,
            can_active=self._can_active,
        )
        self._history.append(snapshot)
        return snapshot

    def get_history(self, limit: int = 100) -> List[StateSnapshot]:
        """Get recent state snapshots."""
        return list(self._history)[-limit:]

    def get_snapshot_at(self, sequence: int) -> Optional[StateSnapshot]:
        """Get a specific snapshot by sequence number."""
        for snap in self._history:
            if snap.sequence == sequence:
                return snap
        return None

    # ========================================================================
    # STALENESS DETECTION
    # ========================================================================

    async def check_staleness(self) -> List[str]:
        """
        Check all signals for staleness.

        A signal is stale if it hasn't been updated within
        (expected_period × multiplier) milliseconds.

        Returns:
            List of stale signal names.
        """
        stale_signals = []
        multiplier = DefaultThresholds.SIGNAL_STALE_MULTIPLIER

        for name, signal in self._signals.items():
            if signal.expected_period_ms <= 0:
                continue  # No staleness check for this signal

            threshold_ms = signal.expected_period_ms * multiplier
            if signal.age_ms > threshold_ms:
                if not signal.is_stale:
                    signal.is_stale = True
                    stale_signals.append(name)
                    logger.warning(
                        f"VSM: signal '{name}' is stale "
                        f"(age={signal.age_ms:.0f}ms, threshold={threshold_ms:.0f}ms)"
                    )

        if stale_signals:
            await self._event_bus.publish(
                EventType.SIGNAL_STALE,
                data={"stale_signals": stale_signals, "count": len(stale_signals)},
                source="state_manager",
            )

        return stale_signals

    def get_stale_signals(self) -> List[str]:
        """Get list of currently stale signals."""
        return [name for name, sig in self._signals.items() if sig.is_stale]

    # ========================================================================
    # CAN STATUS
    # ========================================================================

    def set_can_active(self, active: bool) -> None:
        """Update CAN connection status."""
        if self._can_active != active:
            self._can_active = active
            logger.info(f"VSM: CAN active = {active}")

    @property
    def can_active(self) -> bool:
        return self._can_active

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def last_update(self) -> float:
        return self._last_update

    @property
    def session_duration(self) -> float:
        """Session duration in seconds."""
        return time.time() - self._session_start

    # ========================================================================
    # CHANGE CALLBACKS (Direct notification, faster than event bus)
    # ========================================================================

    def add_change_callback(self, callback: Callable[[str, Any, Any], None]) -> None:
        """
        Register a direct callback for signal changes.
        Called synchronously within the update lock.
        Use for performance-critical paths (e.g., 3D animation).
        """
        self._change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable) -> None:
        """Remove a change callback."""
        try:
            self._change_callbacks.remove(callback)
        except ValueError:
            pass

    # ========================================================================
    # RATE OF CHANGE
    # ========================================================================

    def get_rate_of_change(self, name: str) -> float:
        """Get rate of change (units/second) for a signal."""
        signal = self._signals.get(name)
        return signal.rate_of_change if signal else 0.0

    def get_delta(self, name: str) -> float:
        """Get last change amount for a signal."""
        signal = self._signals.get(name)
        return signal.delta if signal else 0.0

    # ========================================================================
    # RESET & LIFECYCLE
    # ========================================================================

    async def reset(self) -> None:
        """Reset all signals to default values."""
        async with self._lock:
            for signal in self._signals.values():
                signal.value = signal.previous_value  # Keep as previous
                signal.is_stale = False

            self._frame_count = 0
            self._can_active = False
            self._last_update = 0.0
            self._history.clear()
            self._sequence = 0

        await self._event_bus.publish(
            EventType.STATE_RESET,
            data={"timestamp": time.time()},
            source="state_manager",
        )
        logger.info("VSM: state reset")

    def get_stats(self) -> Dict[str, Any]:
        """Get state manager statistics."""
        return {
            "signal_count": len(self._signals),
            "frame_count": self._frame_count,
            "can_active": self._can_active,
            "last_update_age_ms": (time.time() - self._last_update) * 1000 if self._last_update else 0,
            "stale_count": len(self.get_stale_signals()),
            "history_size": len(self._history),
            "sequence": self._sequence,
            "session_duration_s": self.session_duration,
        }