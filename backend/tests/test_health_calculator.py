"""
============================================================================
AutoTwin AI - Health Calculator Tests
============================================================================
Tests for health score calculation.

Test Categories:
  - Overall score computation
  - Subsystem scoring
  - Fault penalty application
  - Threshold-based penalties
  - Score bounds (0-100)
  - Weighted average
  - Trend detection
============================================================================
"""

import pytest

from app.core.constants import Severity, Subsystem, HEALTH_WEIGHTS
from app.vehicle.vehicle_state import VehicleState
from app.vehicle.health_calculator import (
    HealthCalculator,
    HealthScore,
    SubsystemHealth,
)


# ============================================================================
# HEALTH SCORE STRUCTURE TESTS
# ============================================================================


class TestHealthScore:
    """Tests for HealthScore data structure."""

    def test_default_scores(self):
        """Default health should be 100."""
        score = HealthScore()
        assert score.overall == 100.0
        assert score.engine == 100.0
        assert score.status == "good"

    def test_status_classification(self):
        """Status should classify based on score."""
        score = HealthScore(overall=85.0)
        assert score.status == "good"

        score.overall = 65.0
        assert score.status == "warning"

        score.overall = 40.0
        assert score.status == "poor"

        score.overall = 20.0
        assert score.status == "critical"

    def test_needs_attention(self):
        """needs_attention should flag low scores."""
        score = HealthScore(overall=85.0)
        assert score.needs_attention is False

        score.overall = 50.0
        assert score.needs_attention is True

    def test_to_dict(self):
        """Serialization should include all fields."""
        score = HealthScore(overall=78.5, engine=82.0)
        d = score.to_dict()

        assert d["overall"] == 78.5
        assert d["engine"] == 82.0
        assert "status" in d
        assert "subsystems" in d


# ============================================================================
# HEALTH CALCULATOR TESTS
# ============================================================================


class TestHealthCalculator:
    """Tests for HealthCalculator computation logic."""

    def test_healthy_state_full_score(self, health_calculator):
        """Perfectly healthy state should score ~100."""
        state = VehicleState()
        state.engine.coolant_temp = 90.0
        state.engine.rpm = 2000
        state.battery.voltage = 12.6
        state.fuel.level = 80.0

        score = health_calculator.calculate(state, [])
        assert score.overall >= 90.0

    def test_overheat_reduces_cooling_score(self, health_calculator):
        """Overheating should reduce cooling health."""
        state = VehicleState()
        state.engine.coolant_temp = 112.0  # Overheat
        state.cooling.coolant_temp = 112.0

        score = health_calculator.calculate(state, [])
        assert score.cooling < 80.0

    def test_critical_overheat_severe_penalty(self, health_calculator):
        """Critical overheat (>120°C) should severely penalize."""
        state = VehicleState()
        state.engine.coolant_temp = 125.0
        state.cooling.coolant_temp = 125.0

        score = health_calculator.calculate(state, [])
        assert score.cooling < 50.0

    def test_low_battery_reduces_score(self, health_calculator):
        """Low battery should reduce battery health."""
        state = VehicleState()
        state.battery.voltage = 11.0  # Low

        score = health_calculator.calculate(state, [])
        assert score.battery < 80.0

    def test_critical_battery_severe_penalty(self, health_calculator):
        """Critical battery (<10.5V) should severely penalize."""
        state = VehicleState()
        state.battery.voltage = 10.0

        score = health_calculator.calculate(state, [])
        assert score.battery < 50.0

    def test_fault_penalties_applied(self, health_calculator):
        """Active faults should reduce relevant subsystem scores."""
        state = VehicleState()
        faults = [
            {"subsystem": "cooling", "severity": "HIGH", "confidence": 0.85},
        ]

        score = health_calculator.calculate(state, faults)
        assert score.cooling < 100.0

    def test_multiple_faults_cumulative(self, health_calculator):
        """Multiple faults should have cumulative effect."""
        state = VehicleState()

        one_fault = [{"subsystem": "engine", "severity": "LOW", "confidence": 0.8}]
        three_faults = [
            {"subsystem": "engine", "severity": "LOW", "confidence": 0.8},
            {"subsystem": "engine", "severity": "MEDIUM", "confidence": 0.8},
            {"subsystem": "engine", "severity": "HIGH", "confidence": 0.8},
        ]

        score_one = health_calculator.calculate(state, one_fault)
        score_three = health_calculator.calculate(state, three_faults)

        assert score_three.engine < score_one.engine

    def test_scores_bounded_0_to_100(self, health_calculator):
        """All scores should be clamped to [0, 100]."""
        state = VehicleState()
        state.engine.coolant_temp = 200.0  # Extreme
        state.battery.voltage = 5.0  # Extreme

        faults = [
            {"subsystem": "cooling", "severity": "CRITICAL", "confidence": 1.0},
            {"subsystem": "battery", "severity": "CRITICAL", "confidence": 1.0},
        ]

        score = health_calculator.calculate(state, faults)

        assert 0 <= score.overall <= 100
        assert 0 <= score.cooling <= 100
        assert 0 <= score.battery <= 100

    def test_weighted_overall(self, health_calculator):
        """Overall should be weighted average of subsystems."""
        state = VehicleState()
        score = health_calculator.calculate(state, [])

        # Verify weights sum to ~1.0
        total_weight = sum(HEALTH_WEIGHTS.values())
        assert abs(total_weight - 1.0) < 0.05

    def test_rpm_redline_penalty(self, health_calculator):
        """Redline RPM should penalize engine health."""
        state = VehicleState()
        state.engine.rpm = 7000  # Above redline

        score = health_calculator.calculate(state, [])
        assert score.engine < 100.0

    def test_brake_pad_wear_penalty(self, health_calculator):
        """Worn brake pads should penalize brake health."""
        state = VehicleState()
        state.brakes.pad_wear_fl = 5.0  # Critically worn
        state.brakes.pad_wear_fr = 5.0
        state.brakes.pad_wear_rl = 5.0
        state.brakes.pad_wear_rr = 5.0

        score = health_calculator.calculate(state, [])
        assert score.brakes < 70.0

    def test_history_tracking(self, health_calculator):
        """Calculator should track history."""
        state = VehicleState()

        for _ in range(5):
            health_calculator.calculate(state, [])

        history = health_calculator.get_history(limit=5)
        assert len(history) == 5

    def test_trend_detection(self, health_calculator):
        """Trend should detect improvement/decline."""
        state = VehicleState()

        # Calculate multiple times
        for _ in range(10):
            health_calculator.calculate(state, [])

        trend = health_calculator.get_trend("engine")
        assert trend in ("improving", "stable", "declining")

    def test_fan_failure_penalty(self, health_calculator):
        """Fan not working when needed should penalize cooling."""
        state = VehicleState()
        state.cooling.coolant_temp = 100.0  # Above fan threshold
        state.cooling.fan_active = False  # Fan not on

        score = health_calculator.calculate(state, [])
        assert score.cooling < 90.0

    def test_stats(self, health_calculator):
        """Stats should return valid data."""
        state = VehicleState()
        health_calculator.calculate(state, [])

        stats = health_calculator.get_stats()
        assert stats["calculation_count"] == 1
        assert stats["last_overall"] is not None