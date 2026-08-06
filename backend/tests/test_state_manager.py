"""
============================================================================
AutoTwin AI - State Manager Tests
============================================================================
Tests for VehicleStateManager and StateUpdater.

Test Categories:
  - Signal updates (single and batch)
  - Change detection
  - State queries
  - Staleness detection
  - History snapshots
  - StateUpdater signal mapping
  - Special signal handling (doors, indicators, gear)
============================================================================
"""

import asyncio
import time

import pytest
import pytest_asyncio

from app.core.event_bus import EventBus
from app.core.state_manager import VehicleStateManager, SignalValue
from app.vehicle.vehicle_state import VehicleState
from app.vehicle.state_updater import StateUpdater


# ============================================================================
# SIGNAL VALUE TESTS
# ============================================================================


class TestSignalValue:
    """Tests for the SignalValue data structure."""

    def test_initial_state(self):
        """New signal should have default values."""
        sig = SignalValue(name="speed", value=0.0, unit="km/h")
        assert sig.value == 0.0
        assert sig.update_count == 0
        assert sig.is_stale is False

    def test_update_changes_value(self):
        """Update should change value and increment counter."""
        sig = SignalValue(name="speed", value=0.0)

        changed = sig.update(58.0)
        assert changed is True
        assert sig.value == 58.0
        assert sig.previous_value == 0.0
        assert sig.update_count == 1

    def test_update_same_value_returns_false(self):
        """Updating with same value should return False."""
        sig = SignalValue(name="speed", value=58.0)
        changed = sig.update(58.0)
        assert changed is False

    def test_rate_of_change(self):
        """Rate of change should calculate correctly."""
        sig = SignalValue(name="speed", value=0.0)
        sig.timestamp = time.time() - 1.0  # 1 second ago
        sig.previous_value = 0.0
        sig.previous_timestamp = sig.timestamp

        sig.update(60.0)  # 60 km/h change in ~0 seconds
        # Rate will be very high since dt is tiny
        assert sig.rate_of_change >= 0

    def test_delta_calculation(self):
        """Delta should be current - previous."""
        sig = SignalValue(name="speed", value=50.0)
        sig.update(58.0)
        assert sig.delta == 8.0


# ============================================================================
# VEHICLE STATE MANAGER TESTS
# ============================================================================


class TestVehicleStateManager:
    """Tests for the central VehicleStateManager."""

    @pytest.mark.asyncio
    async def test_update_single_signal(self, state_manager):
        """Single signal update should work."""
        changed = await state_manager.update_signal("speed", 58.0)
        assert changed is True
        assert state_manager.get_signal("speed") == 58.0

    @pytest.mark.asyncio
    async def test_update_same_value_no_change(self, state_manager):
        """Updating with same value should report no change."""
        await state_manager.update_signal("speed", 58.0)
        changed = await state_manager.update_signal("speed", 58.0)
        assert changed is False

    @pytest.mark.asyncio
    async def test_batch_update(self, state_manager, sample_signals):
        """Batch update should update multiple signals."""
        changes = await state_manager.update_signals_batch(sample_signals)
        assert changes > 0

        assert state_manager.get_signal("speed") == 58.0
        assert state_manager.get_signal("rpm") == 2450
        assert state_manager.get_signal("fuel") == 82.0

    @pytest.mark.asyncio
    async def test_get_state_dict(self, state_manager, sample_signals):
        """get_state_dict should return all signals."""
        await state_manager.update_signals_batch(sample_signals)
        state = state_manager.get_state_dict()

        assert "speed" in state
        assert "rpm" in state
        assert "fuel" in state
        assert state["speed"] == 58.0

    @pytest.mark.asyncio
    async def test_get_subset(self, state_manager, sample_signals):
        """get_subset should return only requested signals."""
        await state_manager.update_signals_batch(sample_signals)
        subset = state_manager.get_subset(["speed", "rpm"])

        assert "speed" in subset
        assert "rpm" in subset
        assert "fuel" not in subset

    @pytest.mark.asyncio
    async def test_unknown_signal_auto_created(self, state_manager):
        """Unknown signals should be auto-created."""
        await state_manager.update_signal("custom_signal", 42.0)
        assert state_manager.get_signal("custom_signal") == 42.0

    @pytest.mark.asyncio
    async def test_frame_count_increments(self, state_manager):
        """Frame count should increment on changes."""
        initial = state_manager.frame_count
        await state_manager.update_signal("speed", 50.0)
        assert state_manager.frame_count == initial + 1

    @pytest.mark.asyncio
    async def test_can_active_flag(self, state_manager):
        """CAN active flag should update."""
        assert state_manager.can_active is False
        await state_manager.update_signal("speed", 50.0)
        assert state_manager.can_active is True

    @pytest.mark.asyncio
    async def test_state_snapshot(self, state_manager, sample_signals):
        """Snapshot should capture current state."""
        await state_manager.update_signals_batch(sample_signals)
        snapshot = state_manager.take_snapshot()

        assert snapshot.sequence == 1
        assert snapshot.signals["speed"] == 58.0
        assert snapshot.can_active is True

    @pytest.mark.asyncio
    async def test_history_retrieval(self, state_manager):
        """History should store multiple snapshots."""
        for i in range(5):
            await state_manager.update_signal("speed", float(i * 10))
            state_manager.take_snapshot()

        history = state_manager.get_history(limit=5)
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_reset(self, state_manager, sample_signals):
        """Reset should clear state."""
        await state_manager.update_signals_batch(sample_signals)
        await state_manager.reset()

        assert state_manager.frame_count == 0
        assert state_manager.can_active is False

    @pytest.mark.asyncio
    async def test_change_callback(self, state_manager):
        """Change callbacks should be invoked on update."""
        received = []

        def callback(name, new_val, old_val):
            received.append((name, new_val, old_val))

        state_manager.add_change_callback(callback)
        await state_manager.update_signal("speed", 58.0)

        assert len(received) == 1
        assert received[0][0] == "speed"
        assert received[0][1] == 58.0

    @pytest.mark.asyncio
    async def test_get_stats(self, state_manager):
        """Stats should return valid data."""
        stats = state_manager.get_stats()
        assert "signal_count" in stats
        assert "frame_count" in stats
        assert stats["signal_count"] > 0


# ============================================================================
# STATE UPDATER TESTS
# ============================================================================


class TestStateUpdater:
    """Tests for the StateUpdater (CAN → VehicleState mapping)."""

    def test_apply_basic_signals(self, state_updater, vehicle_state, sample_signals):
        """Basic signal application should work."""
        changes = state_updater.apply(vehicle_state, sample_signals)
        assert changes > 0
        assert vehicle_state.body.speed == 58.0
        assert vehicle_state.engine.rpm == 2450

    def test_apply_gear_string(self, state_updater, vehicle_state):
        """Gear should be applied as string."""
        state_updater.apply(vehicle_state, {"gear": "D"})
        assert vehicle_state.transmission.gear == "D"

    def test_apply_gear_integer(self, state_updater, vehicle_state):
        """Gear integer should map to string."""
        state_updater.apply(vehicle_state, {"gear": 3})
        assert vehicle_state.transmission.gear == "D"

    def test_apply_door_bitmask(self, state_updater, vehicle_state):
        """Door bitmask should set individual booleans."""
        state_updater.apply(vehicle_state, {"door": 3})  # FL + FR
        assert vehicle_state.body.door_fl is True
        assert vehicle_state.body.door_fr is True
        assert vehicle_state.body.door_rl is False

    def test_apply_door_string(self, state_updater, vehicle_state):
        """Door string should set individual booleans."""
        state_updater.apply(vehicle_state, {"door": "FL RR"})
        assert vehicle_state.body.door_fl is True
        assert vehicle_state.body.door_rr is True
        assert vehicle_state.body.door_fr is False

    def test_apply_door_closed(self, state_updater, vehicle_state):
        """'Closed' should set all doors to False."""
        state_updater.apply(vehicle_state, {"door": 5})  # Open some
        state_updater.apply(vehicle_state, {"door": "Closed"})
        assert vehicle_state.body.any_door_open is False

    def test_apply_indicator_bitmask(self, state_updater, vehicle_state):
        """Indicator bitmask should set individual booleans."""
        state_updater.apply(vehicle_state, {"indicator": 1})  # Left
        assert vehicle_state.body.turn_left is True
        assert vehicle_state.body.turn_right is False

        state_updater.apply(vehicle_state, {"indicator": 4})  # Hazard
        assert vehicle_state.body.hazard is True

    def test_apply_brake_boolean(self, state_updater, vehicle_state):
        """Brake 0/1 should map to boolean."""
        state_updater.apply(vehicle_state, {"brake": 1})
        assert vehicle_state.brakes.applied is True

        state_updater.apply(vehicle_state, {"brake": 0})
        assert vehicle_state.brakes.applied is False

    def test_apply_temperature_side_effect(self, state_updater, vehicle_state):
        """Temperature update should sync to cooling subsystem."""
        state_updater.apply(vehicle_state, {"temp": 95})
        assert vehicle_state.cooling.coolant_temp == 95

    def test_apply_rpm_engine_on(self, state_updater, vehicle_state):
        """RPM > 100 should set engine_on = True."""
        state_updater.apply(vehicle_state, {"rpm": 2000})
        assert vehicle_state.engine.engine_on is True

    def test_apply_no_change_returns_zero(self, state_updater, vehicle_state):
        """Applying same values should return 0 changes."""
        signals = {"speed": 50.0}
        state_updater.apply(vehicle_state, signals)
        changes = state_updater.apply(vehicle_state, signals)
        assert changes == 0

    def test_stats(self, state_updater, vehicle_state, sample_signals):
        """Updater stats should track operations."""
        state_updater.apply(vehicle_state, sample_signals)
        stats = state_updater.get_stats()
        assert stats["update_count"] == 1
        assert stats["total_changes"] > 0