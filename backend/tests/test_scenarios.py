"""
============================================================================
AutoTwin AI - Scenario Tests
============================================================================
Tests for scenario engine, definitions, and replay.

Test Categories:
  - Scenario library (built-in scenarios)
  - Scenario definition structure
  - Scenario step retrieval
  - Scenario engine start/stop
  - Replay engine load/play/seek
============================================================================
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from app.core.event_bus import EventBus
from app.scenarios.scenario_engine import ScenarioEngine
from app.scenarios.scenario_definitions import (
    ScenarioDefinition,
    ScenarioStep,
    ScenarioLibrary,
)
from app.scenarios.replay_engine import ReplayEngine


# ============================================================================
# SCENARIO LIBRARY TESTS
# ============================================================================


class TestScenarioLibrary:
    """Tests for the built-in scenario library."""

    def test_library_loads_scenarios(self, scenario_library):
        """Library should load all built-in scenarios."""
        scenarios = scenario_library.get_all()
        assert len(scenarios) >= 9

    def test_required_scenarios_exist(self, scenario_library):
        """All required scenarios should be present."""
        required_ids = [
            "normal_driving",
            "city_traffic",
            "highway_cruise",
            "engine_overheat",
            "battery_failure",
            "abs_activation",
            "door_open_driving",
            "engine_stall",
            "fuel_leak",
        ]

        for scenario_id in required_ids:
            scenario = scenario_library.get(scenario_id)
            assert scenario is not None, f"Missing scenario: {scenario_id}"

    def test_scenario_has_steps(self, scenario_library):
        """Each scenario should have at least one step."""
        for scenario in scenario_library.get_all():
            assert scenario.step_count > 0, f"{scenario.scenario_id} has no steps"

    def test_scenario_has_duration(self, scenario_library):
        """Each scenario should have positive duration."""
        for scenario in scenario_library.get_all():
            assert scenario.duration_s > 0, f"{scenario.scenario_id} has no duration"

    def test_scenario_steps_have_signals(self, scenario_library):
        """Scenario steps should contain signal injections."""
        scenario = scenario_library.get("normal_driving")
        assert scenario is not None

        # At least one step should have signals
        has_signals = any(len(step.signals) > 0 for step in scenario.steps)
        assert has_signals

    def test_scenario_steps_ordered_by_time(self, scenario_library):
        """Steps should be ordered by time."""
        scenario = scenario_library.get("normal_driving")

        for i in range(1, len(scenario.steps)):
            assert scenario.steps[i].time_s >= scenario.steps[i - 1].time_s

    def test_get_step_at_time(self, scenario_library):
        """get_step_at should return correct step."""
        scenario = scenario_library.get("engine_overheat")

        # At t=0, should be first step
        step = scenario.get_step_at(0)
        assert step is not None
        assert step.time_s == 0

        # At t=25, should be a later step with higher temp
        step = scenario.get_step_at(25)
        assert step is not None
        assert step.time_s <= 25

    def test_overheat_scenario_temps_rise(self, scenario_library):
        """Overheat scenario should show rising temperature."""
        scenario = scenario_library.get("engine_overheat")

        temps = []
        for step in scenario.steps:
            if "temp" in step.signals:
                temps.append(step.signals["temp"])

        # Temperature should generally increase
        assert len(temps) >= 3
        assert temps[-1] > temps[0]  # Final temp > initial temp

    def test_get_by_category(self, scenario_library):
        """Category filtering should work."""
        fault_scenarios = scenario_library.get_by_category("fault")
        assert len(fault_scenarios) >= 5

        normal_scenarios = scenario_library.get_by_category("normal")
        assert len(normal_scenarios) >= 2

    def test_nonexistent_scenario_returns_none(self, scenario_library):
        """Non-existent scenario should return None."""
        result = scenario_library.get("nonexistent_scenario")
        assert result is None

    def test_scenario_to_dict(self, scenario_library):
        """Scenario serialization should include all fields."""
        scenario = scenario_library.get("normal_driving")
        d = scenario.to_dict()

        assert "scenario_id" in d
        assert "name" in d
        assert "duration_s" in d
        assert "step_count" in d
        assert "category" in d


# ============================================================================
# SCENARIO DEFINITION TESTS
# ============================================================================


class TestScenarioDefinition:
    """Tests for ScenarioDefinition structure."""

    def test_create_scenario(self):
        """Should create scenario with steps."""
        scenario = ScenarioDefinition(
            scenario_id="test",
            name="Test Scenario",
            duration_s=30.0,
            steps=[
                ScenarioStep(0, {"speed": 0, "rpm": 800}),
                ScenarioStep(10, {"speed": 30, "rpm": 1500}),
                ScenarioStep(20, {"speed": 60, "rpm": 2200}),
            ],
        )

        assert scenario.step_count == 3
        assert scenario.duration_s == 30.0

    def test_step_retrieval(self):
        """Step retrieval at various times."""
        scenario = ScenarioDefinition(
            scenario_id="test",
            name="Test",
            duration_s=30.0,
            steps=[
                ScenarioStep(0, {"speed": 0}),
                ScenarioStep(10, {"speed": 30}),
                ScenarioStep(20, {"speed": 60}),
            ],
        )

        # Before first step
        step = scenario.get_step_at(0)
        assert step.signals["speed"] == 0

        # Between steps
        step = scenario.get_step_at(15)
        assert step.signals["speed"] == 30  # Step at t=10

        # After last step start
        step = scenario.get_step_at(25)
        assert step.signals["speed"] == 60  # Step at t=20


# ============================================================================
# SCENARIO ENGINE TESTS
# ============================================================================


class TestScenarioEngine:
    """Tests for the ScenarioEngine execution."""

    @pytest.mark.asyncio
    async def test_start_scenario(self):
        """Should start a scenario successfully."""
        bus = EventBus()
        engine = ScenarioEngine(bus)

        success = await engine.start("normal_driving")
        assert success is True
        assert engine.is_running is True

        await engine.stop()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_start_nonexistent_scenario(self):
        """Starting non-existent scenario should fail."""
        bus = EventBus()
        engine = ScenarioEngine(bus)

        success = await engine.start("nonexistent")
        assert success is False

        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_stop_scenario(self):
        """Should stop a running scenario."""
        bus = EventBus()
        engine = ScenarioEngine(bus)

        await engine.start("normal_driving")
        assert engine.is_running is True

        await engine.stop()
        assert engine.is_running is False

        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_cannot_start_two_scenarios(self):
        """Should not allow two scenarios simultaneously."""
        bus = EventBus()
        engine = ScenarioEngine(bus)

        await engine.start("normal_driving")
        success = await engine.start("highway_cruise")
        assert success is False

        await engine.stop()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_get_active_scenario(self):
        """Should return active scenario info."""
        bus = EventBus()
        engine = ScenarioEngine(bus)

        await engine.start("engine_overheat")
        active = engine.get_active_scenario()

        assert active is not None
        assert active["scenario_id"] == "engine_overheat"
        assert "progress" in active

        await engine.stop()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_get_available_scenarios(self):
        """Should list all available scenarios."""
        bus = EventBus()
        engine = ScenarioEngine(bus)

        scenarios = engine.get_available_scenarios()
        assert len(scenarios) >= 9

        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_scenario_stats(self):
        """Stats should track execution."""
        bus = EventBus()
        engine = ScenarioEngine(bus)

        await engine.start("normal_driving")
        await asyncio.sleep(0.1)
        await engine.stop()

        stats = engine.get_stats()
        assert stats["scenarios_run"] >= 1

        await bus.shutdown()


# ============================================================================
# REPLAY ENGINE TESTS
# ============================================================================


class TestReplayEngine:
    """Tests for the ReplayEngine."""

    @pytest.fixture
    def sample_log_data(self):
        """Sample replay log data."""
        return {
            "metadata": {
                "vehicle": "test_vehicle",
                "duration_s": 10.0,
                "frame_count": 5,
            },
            "frames": [
                {"timestamp": 0.0, "signals": {"speed": 0, "rpm": 800}},
                {"timestamp": 2.0, "signals": {"speed": 20, "rpm": 1200}},
                {"timestamp": 4.0, "signals": {"speed": 40, "rpm": 1800}},
                {"timestamp": 6.0, "signals": {"speed": 60, "rpm": 2200}},
                {"timestamp": 8.0, "signals": {"speed": 50, "rpm": 2000}},
            ],
        }

    @pytest.fixture
    def sample_log_file(self, sample_log_data):
        """Create a temporary log file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(sample_log_data, f)
            return f.name

    @pytest.mark.asyncio
    async def test_load_log(self, sample_log_file):
        """Should load a log file successfully."""
        bus = EventBus()
        engine = ReplayEngine(bus)

        loaded = await engine.load(sample_log_file)
        assert loaded is True
        assert engine.is_loaded is True
        assert engine.duration == 10.0

        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self):
        """Loading non-existent file should fail."""
        bus = EventBus()
        engine = ReplayEngine(bus)

        loaded = await engine.load("/nonexistent/path.json")
        assert loaded is False

        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_load_from_frames(self, sample_log_data):
        """Should load from frame list directly."""
        bus = EventBus()
        engine = ReplayEngine(bus)

        loaded = engine.load_from_frames(
            sample_log_data["frames"],
            sample_log_data["metadata"],
        )
        assert loaded is True
        assert engine.duration == 10.0

        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_play_and_stop(self, sample_log_data):
        """Should play and stop without error."""
        bus = EventBus()
        engine = ReplayEngine(bus)
        engine.load_from_frames(sample_log_data["frames"], sample_log_data["metadata"])

        await engine.play(speed=1.0)
        assert engine.is_playing is True

        await asyncio.sleep(0.1)

        await engine.stop()
        assert engine.is_playing is False

        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_pause_resume(self, sample_log_data):
        """Should pause and resume."""
        bus = EventBus()
        engine = ReplayEngine(bus)
        engine.load_from_frames(sample_log_data["frames"], sample_log_data["metadata"])

        await engine.play()
        await engine.pause()
        assert engine._paused is True

        await engine.resume()
        assert engine._paused is False

        await engine.stop()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_seek(self, sample_log_data):
        """Should seek to position."""
        bus = EventBus()
        engine = ReplayEngine(bus)
        engine.load_from_frames(sample_log_data["frames"], sample_log_data["metadata"])

        await engine.seek(5.0)
        assert engine.position == 5.0

        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_speed_control(self, sample_log_data):
        """Should change playback speed."""
        bus = EventBus()
        engine = ReplayEngine(bus)
        engine.load_from_frames(sample_log_data["frames"], sample_log_data["metadata"])

        engine.set_speed(2.0)
        assert engine._speed == 2.0

        engine.set_speed(0.5)
        assert engine._speed == 0.5

        # Clamp to max
        engine.set_speed(100.0)
        assert engine._speed == 10.0

        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_progress_tracking(self, sample_log_data):
        """Progress should advance during playback."""
        bus = EventBus()
        engine = ReplayEngine(bus)
        engine.load_from_frames(sample_log_data["frames"], sample_log_data["metadata"])

        assert engine.progress == 0.0

        await engine.play(speed=10.0)  # Fast speed
        await asyncio.sleep(0.2)

        # Progress should have advanced
        assert engine.progress > 0.0

        await engine.stop()
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_stats(self, sample_log_data):
        """Stats should return valid data."""
        bus = EventBus()
        engine = ReplayEngine(bus)
        engine.load_from_frames(sample_log_data["frames"], sample_log_data["metadata"])

        stats = engine.get_stats()
        assert stats["loaded"] is True
        assert stats["frame_count"] == 5
        assert stats["duration_s"] == 10.0

        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_play_without_load_fails(self):
        """Playing without loading should fail."""
        bus = EventBus()
        engine = ReplayEngine(bus)

        result = await engine.play()
        assert result is False

        await bus.shutdown()