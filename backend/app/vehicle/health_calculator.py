"""
============================================================================
AutoTwin AI - Health Score Calculator
============================================================================
Computes vehicle health scores based on current state, fault history,
and signal degradation patterns.

Health Score Model:
  - Each subsystem gets a score from 0-100
  - Overall health is a weighted average of subsystem scores
  - Scores decrease based on:
    • Active faults (severity-weighted)
    • Signal threshold violations
    • Rate of degradation
    • Historical fault frequency
  - Scores recover slowly during normal operation

Scoring Formula:
  subsystem_score = 100 - fault_penalty - threshold_penalty - degradation_penalty

  fault_penalty = Σ(severity_weight × confidence) for active faults
  threshold_penalty = proportional to how far signals exceed thresholds
  degradation_penalty = based on rate-of-change trends

Usage:
    calculator = HealthCalculator(event_bus)
    scores = calculator.calculate(vehicle_state, active_faults)
    # scores.overall = 78.5
    # scores.engine = 82.0
    # scores.cooling = 62.0
============================================================================
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.constants import (
    EventType,
    Severity,
    Subsystem,
    HEALTH_WEIGHTS,
    HEALTH_SCORE_MAX,
    HEALTH_SCORE_MIN,
    HEALTH_SCORE_CRITICAL,
    HEALTH_SCORE_WARNING,
    DefaultThresholds,
)
from app.core.event_bus import EventBus
from app.vehicle.vehicle_state import VehicleState


# ============================================================================
# HEALTH SCORE DATA STRUCTURES
# ============================================================================


@dataclass
class SubsystemHealth:
    """Health score for a single subsystem."""

    name: str
    score: float = 100.0
    previous_score: float = 100.0
    trend: str = "stable"  # "improving", "stable", "declining", "critical"
    active_faults: int = 0
    penalty_from_faults: float = 0.0
    penalty_from_thresholds: float = 0.0
    last_updated: float = field(default_factory=time.time)

    @property
    def status(self) -> str:
        if self.score >= 80:
            return "good"
        elif self.score >= 60:
            return "warning"
        elif self.score >= HEALTH_SCORE_CRITICAL:
            return "poor"
        else:
            return "critical"

    @property
    def delta(self) -> float:
        return self.score - self.previous_score


@dataclass
class HealthScore:
    """Complete health score result."""

    overall: float = 100.0
    engine: float = 100.0
    transmission: float = 100.0
    brakes: float = 100.0
    cooling: float = 100.0
    battery: float = 100.0
    electrical: float = 100.0
    fuel: float = 100.0

    subsystems: Dict[str, SubsystemHealth] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    active_fault_count: int = 0

    @property
    def status(self) -> str:
        if self.overall >= 80:
            return "good"
        elif self.overall >= 60:
            return "warning"
        elif self.overall >= HEALTH_SCORE_CRITICAL:
            return "poor"
        else:
            return "critical"

    @property
    def needs_attention(self) -> bool:
        return self.overall < HEALTH_SCORE_WARNING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": round(self.overall, 1),
            "engine": round(self.engine, 1),
            "transmission": round(self.transmission, 1),
            "brakes": round(self.brakes, 1),
            "cooling": round(self.cooling, 1),
            "battery": round(self.battery, 1),
            "electrical": round(self.electrical, 1),
            "fuel": round(self.fuel, 1),
            "status": self.status,
            "active_fault_count": self.active_fault_count,
            "timestamp": self.timestamp,
            "subsystems": {
                name: {
                    "score": round(sh.score, 1),
                    "status": sh.status,
                    "trend": sh.trend,
                    "active_faults": sh.active_faults,
                }
                for name, sh in self.subsystems.items()
            },
        }


# ============================================================================
# HEALTH CALCULATOR
# ============================================================================


class HealthCalculator:
    """
    Calculates vehicle health scores from state and fault data.

    Scoring Strategy:
      1. Start at 100 for each subsystem
      2. Subtract penalties for active faults
      3. Subtract penalties for threshold violations
      4. Apply degradation trends
      5. Clamp to [0, 100]
      6. Compute weighted overall score
    """

    # Severity penalty weights
    SEVERITY_PENALTIES = {
        Severity.INFO: 1.0,
        Severity.LOW: 3.0,
        Severity.MEDIUM: 8.0,
        Severity.HIGH: 15.0,
        Severity.CRITICAL: 30.0,
    }

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus
        self._last_scores: Optional[HealthScore] = None
        self._history: List[HealthScore] = []
        self._max_history: int = 1000
        self._calculation_count: int = 0

    # ========================================================================
    # MAIN CALCULATION
    # ========================================================================

    def calculate(
        self,
        state: VehicleState,
        active_faults: Optional[List[Dict[str, Any]]] = None,
    ) -> HealthScore:
        """
        Calculate complete health score from vehicle state and faults.

        Args:
            state: Current vehicle state
            active_faults: List of active fault dictionaries

        Returns:
            HealthScore with all subsystem scores.
        """
        faults = active_faults or []

        # Calculate each subsystem
        engine_health = self._calc_engine(state, faults)
        transmission_health = self._calc_transmission(state, faults)
        brake_health = self._calc_brakes(state, faults)
        cooling_health = self._calc_cooling(state, faults)
        battery_health = self._calc_battery(state, faults)
        electrical_health = self._calc_electrical(state, faults)
        fuel_health = self._calc_fuel(state, faults)

        # Build subsystem health objects
        subsystems = {
            Subsystem.ENGINE.value: engine_health,
            Subsystem.TRANSMISSION.value: transmission_health,
            Subsystem.BRAKES.value: brake_health,
            Subsystem.COOLING.value: cooling_health,
            Subsystem.BATTERY.value: battery_health,
            Subsystem.ELECTRICAL.value: electrical_health,
            Subsystem.FUEL.value: fuel_health,
        }

        # Calculate weighted overall
        overall = self._calc_overall(subsystems)

        # Build result
        result = HealthScore(
            overall=overall,
            engine=engine_health.score,
            transmission=transmission_health.score,
            brakes=brake_health.score,
            cooling=cooling_health.score,
            battery=battery_health.score,
            electrical=electrical_health.score,
            fuel=fuel_health.score,
            subsystems=subsystems,
            active_fault_count=len(faults),
        )

        # Store history
        self._history.append(result)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        self._last_scores = result
        self._calculation_count += 1

        return result

    # ========================================================================
    # SUBSYSTEM CALCULATIONS
    # ========================================================================

    def _calc_engine(self, state: VehicleState, faults: List[Dict]) -> SubsystemHealth:
        """Calculate engine health score."""
        score = 100.0
        fault_count = 0

        # Fault penalties
        for fault in faults:
            if fault.get("subsystem") == Subsystem.ENGINE.value:
                severity = Severity.from_string(fault.get("severity", "LOW"))
                confidence = fault.get("confidence", 0.8)
                score -= self.SEVERITY_PENALTIES[severity] * confidence
                fault_count += 1

        # Threshold penalties
        engine = state.engine

        # RPM redline
        if engine.rpm > DefaultThresholds.RPM_REDLINE:
            excess = (engine.rpm - DefaultThresholds.RPM_REDLINE) / 1500.0
            score -= min(10.0, excess * 5.0)

        # Overheating
        if engine.coolant_temp > DefaultThresholds.TEMP_HIGH:
            excess = (engine.coolant_temp - DefaultThresholds.TEMP_HIGH) / 15.0
            score -= min(20.0, excess * 8.0)

        # High load sustained
        if engine.load > 90:
            score -= 3.0

        # Misfires
        score -= min(10.0, engine.misfire_count * 2.0)

        return SubsystemHealth(
            name=Subsystem.ENGINE.value,
            score=max(HEALTH_SCORE_MIN, min(HEALTH_SCORE_MAX, score)),
            previous_score=self._get_previous_score(Subsystem.ENGINE.value),
            active_faults=fault_count,
        )

    def _calc_transmission(self, state: VehicleState, faults: List[Dict]) -> SubsystemHealth:
        """Calculate transmission health score."""
        score = 100.0
        fault_count = 0

        for fault in faults:
            if fault.get("subsystem") == Subsystem.TRANSMISSION.value:
                severity = Severity.from_string(fault.get("severity", "LOW"))
                confidence = fault.get("confidence", 0.8)
                score -= self.SEVERITY_PENALTIES[severity] * confidence
                fault_count += 1

        # High RPM in low gear (potential slipping)
        trans = state.transmission
        if trans.gear in ("D", "S") and state.engine.rpm > 5000 and state.body.speed < 30:
            score -= 10.0  # Possible transmission slip

        return SubsystemHealth(
            name=Subsystem.TRANSMISSION.value,
            score=max(HEALTH_SCORE_MIN, min(HEALTH_SCORE_MAX, score)),
            previous_score=self._get_previous_score(Subsystem.TRANSMISSION.value),
            active_faults=fault_count,
        )

    def _calc_brakes(self, state: VehicleState, faults: List[Dict]) -> SubsystemHealth:
        """Calculate brake health score."""
        score = 100.0
        fault_count = 0

        for fault in faults:
            if fault.get("subsystem") == Subsystem.BRAKES.value:
                severity = Severity.from_string(fault.get("severity", "LOW"))
                confidence = fault.get("confidence", 0.8)
                score -= self.SEVERITY_PENALTIES[severity] * confidence
                fault_count += 1

        brakes = state.brakes

        # Pad wear penalty
        avg_wear = brakes.avg_pad_wear
        if avg_wear < 20:
            score -= (20 - avg_wear) * 1.5  # Up to -30 for 0% wear
        elif avg_wear < 40:
            score -= (40 - avg_wear) * 0.5  # Up to -10

        # ABS activation (indicates hard braking or wheel slip)
        if brakes.abs_active:
            score -= 2.0

        # Wheel speed difference (potential brake drag)
        if state.wheel_speed.has_wheel_slip and state.brakes.applied:
            score -= 5.0

        return SubsystemHealth(
            name=Subsystem.BRAKES.value,
            score=max(HEALTH_SCORE_MIN, min(HEALTH_SCORE_MAX, score)),
            previous_score=self._get_previous_score(Subsystem.BRAKES.value),
            active_faults=fault_count,
        )

    def _calc_cooling(self, state: VehicleState, faults: List[Dict]) -> SubsystemHealth:
        """Calculate cooling system health score."""
        score = 100.0
        fault_count = 0

        for fault in faults:
            if fault.get("subsystem") == Subsystem.COOLING.value:
                severity = Severity.from_string(fault.get("severity", "LOW"))
                confidence = fault.get("confidence", 0.8)
                score -= self.SEVERITY_PENALTIES[severity] * confidence
                fault_count += 1

        cooling = state.cooling

        # Temperature-based penalties
        if cooling.coolant_temp > DefaultThresholds.TEMP_CRITICAL:
            score -= 35.0  # Critical overheat
        elif cooling.coolant_temp > DefaultThresholds.TEMP_HIGH:
            excess = cooling.coolant_temp - DefaultThresholds.TEMP_HIGH
            score -= min(25.0, excess * 1.5)
        elif cooling.coolant_temp > DefaultThresholds.TEMP_WARNING:
            score -= 5.0

        # Fan not working when needed
        if cooling.fan_should_be_on and not cooling.fan_active:
            score -= 15.0  # Fan failure suspected

        # Coolant level
        if cooling.coolant_level < 50:
            score -= 10.0

        return SubsystemHealth(
            name=Subsystem.COOLING.value,
            score=max(HEALTH_SCORE_MIN, min(HEALTH_SCORE_MAX, score)),
            previous_score=self._get_previous_score(Subsystem.COOLING.value),
            active_faults=fault_count,
        )

    def _calc_battery(self, state: VehicleState, faults: List[Dict]) -> SubsystemHealth:
        """Calculate battery health score."""
        score = 100.0
        fault_count = 0

        for fault in faults:
            if fault.get("subsystem") == Subsystem.BATTERY.value:
                severity = Severity.from_string(fault.get("severity", "LOW"))
                confidence = fault.get("confidence", 0.8)
                score -= self.SEVERITY_PENALTIES[severity] * confidence
                fault_count += 1

        battery = state.battery

        # Voltage-based penalties
        if battery.voltage < DefaultThresholds.BATTERY_CRITICAL:
            score -= 40.0
        elif battery.voltage < DefaultThresholds.BATTERY_LOW:
            score -= 20.0
        elif battery.voltage < DefaultThresholds.BATTERY_NORMAL_MIN:
            score -= 8.0

        # Overcharging
        if battery.voltage > DefaultThresholds.BATTERY_OVERCHARGE:
            score -= 15.0

        # Battery health degradation
        if battery.health < 50:
            score -= (50 - battery.health) * 0.5

        return SubsystemHealth(
            name=Subsystem.BATTERY.value,
            score=max(HEALTH_SCORE_MIN, min(HEALTH_SCORE_MAX, score)),
            previous_score=self._get_previous_score(Subsystem.BATTERY.value),
            active_faults=fault_count,
        )

    def _calc_electrical(self, state: VehicleState, faults: List[Dict]) -> SubsystemHealth:
        """Calculate electrical system health score."""
        score = 100.0
        fault_count = 0

        for fault in faults:
            if fault.get("subsystem") == Subsystem.ELECTRICAL.value:
                severity = Severity.from_string(fault.get("severity", "LOW"))
                confidence = fault.get("confidence", 0.8)
                score -= self.SEVERITY_PENALTIES[severity] * confidence
                fault_count += 1

        electrical = state.electrical

        # Voltage fluctuation
        if electrical.ground_fault:
            score -= 20.0

        if electrical.fuse_blown:
            score -= 15.0

        return SubsystemHealth(
            name=Subsystem.ELECTRICAL.value,
            score=max(HEALTH_SCORE_MIN, min(HEALTH_SCORE_MAX, score)),
            previous_score=self._get_previous_score(Subsystem.ELECTRICAL.value),
            active_faults=fault_count,
        )

    def _calc_fuel(self, state: VehicleState, faults: List[Dict]) -> SubsystemHealth:
        """Calculate fuel system health score."""
        score = 100.0
        fault_count = 0

        for fault in faults:
            if fault.get("subsystem") == Subsystem.FUEL.value:
                severity = Severity.from_string(fault.get("severity", "LOW"))
                confidence = fault.get("confidence", 0.8)
                score -= self.SEVERITY_PENALTIES[severity] * confidence
                fault_count += 1

        fuel = state.fuel

        # Very low fuel isn't a "health" issue per se, but indicates risk
        if fuel.level < DefaultThresholds.FUEL_CRITICAL:
            score -= 5.0

        # Abnormal fuel pressure
        if fuel.pressure < 1.0 or fuel.pressure > 6.0:
            score -= 15.0

        return SubsystemHealth(
            name=Subsystem.FUEL.value,
            score=max(HEALTH_SCORE_MIN, min(HEALTH_SCORE_MAX, score)),
            previous_score=self._get_previous_score(Subsystem.FUEL.value),
            active_faults=fault_count,
        )

    # ========================================================================
    # OVERALL SCORE
    # ========================================================================

    def _calc_overall(self, subsystems: Dict[str, SubsystemHealth]) -> float:
        """Calculate weighted overall health score."""
        total_weight = 0.0
        weighted_sum = 0.0

        for name, health in subsystems.items():
            weight = HEALTH_WEIGHTS.get(name, 0.05)
            weighted_sum += health.score * weight
            total_weight += weight

        if total_weight == 0:
            return 100.0

        return weighted_sum / total_weight

    # ========================================================================
    # HELPERS
    # ========================================================================

    def _get_previous_score(self, subsystem: str) -> float:
        """Get previous score for trend calculation."""
        if self._last_scores and subsystem in self._last_scores.subsystems:
            return self._last_scores.subsystems[subsystem].score
        return 100.0

    def get_trend(self, subsystem: str, window: int = 5) -> str:
        """Determine health trend over recent calculations."""
        if len(self._history) < window:
            return "stable"

        recent = self._history[-window:]
        scores = []
        for h in recent:
            if subsystem in h.subsystems:
                scores.append(h.subsystems[subsystem].score)

        if len(scores) < 2:
            return "stable"

        delta = scores[-1] - scores[0]
        if delta > 2:
            return "improving"
        elif delta < -2:
            return "declining"
        return "stable"

    # ========================================================================
    # PERIODIC UPDATE TASK
    # ========================================================================

    async def periodic_update(self, interval_s: int = 10) -> None:
        """
        Background task: periodically recalculate health scores.

        Called from FastAPI lifespan. Runs until cancelled.
        """
        logger.info(f"HealthCalculator: periodic updates every {interval_s}s")

        while True:
            try:
                await asyncio.sleep(interval_s)
                # Actual calculation is triggered by the broadcast service
                # which has access to current state and faults.
                # This task just ensures periodic emission.
                if self._event_bus:
                    await self._event_bus.publish(
                        EventType.HEALTH_UPDATED,
                        data={"trigger": "periodic", "interval_s": interval_s},
                        source="health_calculator",
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"HealthCalculator: periodic update error: {e}")

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_history(self, limit: int = 100) -> List[HealthScore]:
        """Get recent health score history."""
        return self._history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "calculation_count": self._calculation_count,
            "history_size": len(self._history),
            "last_overall": self._last_scores.overall if self._last_scores else None,
            "last_status": self._last_scores.status if self._last_scores else None,
        }