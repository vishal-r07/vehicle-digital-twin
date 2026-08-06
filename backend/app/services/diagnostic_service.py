"""
============================================================================
AutoTwin AI - Diagnostic Service
============================================================================
Orchestrates the complete diagnostic pipeline:
  State → Fault Detection → Health Scoring → Timeline → Recommendations

This service coordinates:
  - FaultEngine (rule evaluation)
  - HealthCalculator (score computation)
  - FaultTimeline (event logging)
  - RecommendationEngine (repair advice)

Usage:
    service = DiagnosticService(fault_engine, health_calculator, event_bus)
    await service.process_state_update(state_dict)
    faults = service.get_active_faults()
    health = await service.get_health_scores()
============================================================================
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.constants import EventType, Severity
from app.core.event_bus import EventBus
from app.diagnostics.fault_engine import FaultEngine, FaultEvent
from app.diagnostics.fault_timeline import FaultTimeline
from app.diagnostics.recommendations import RecommendationEngine, RepairRecommendation
from app.vehicle.health_calculator import HealthCalculator, HealthScore
from app.vehicle.vehicle_state import VehicleState


# ============================================================================
# DIAGNOSTIC SERVICE
# ============================================================================


class DiagnosticService:
    """
    Orchestrates the diagnostic pipeline.

    Coordinates fault detection, health scoring, timeline logging,
    and recommendation generation into a unified service.
    """

    def __init__(
        self,
        fault_engine: FaultEngine,
        health_calculator: HealthCalculator,
        event_bus: EventBus,
        state_manager=None,
    ):
        self._fault_engine = fault_engine
        self._health_calculator = health_calculator
        self._event_bus = event_bus
        self._state_manager = state_manager
        self._recommendation_engine = RecommendationEngine()

        # Last computed values (cached)
        self._last_health: Optional[HealthScore] = None
        self._last_health_time: float = 0.0
        self._health_cache_ttl: float = 5.0  # seconds

        # Statistics
        self._processing_count: int = 0
        self._total_faults_detected: int = 0

        logger.info("DiagnosticService: initialized")

    # ========================================================================
    # MAIN PROCESSING PIPELINE
    # ========================================================================

    async def process_state_update(self, signals: Dict[str, Any]) -> List[FaultEvent]:
        """
        Process a vehicle state update through the diagnostic pipeline.

        Steps:
          1. Evaluate fault rules against signals
          2. Log any new faults to timeline
          3. Recalculate health scores
          4. Emit events for WebSocket broadcast

        Args:
            signals: Dictionary of current signal values

        Returns:
            List of newly triggered FaultEvents
        """
        self._processing_count += 1

        # Step 1: Evaluate fault rules
        new_faults = self._fault_engine.evaluate_state(signals)

        # Step 2: Handle new faults
        for fault in new_faults:
            self._total_faults_detected += 1

            # Log to timeline
            self._fault_engine._timeline.log_fault(fault)

            # Emit fault event
            await self._event_bus.publish(
                EventType.FAULT_DETECTED,
                data=fault.to_dict(),
                source="diagnostic_service",
                priority=5,
            )

            logger.warning(
                f"DiagnosticService: FAULT [{fault.severity}] "
                f"{fault.rule_id}: {fault.message}"
            )

        # Step 3: Check for resolved faults
        await self._check_fault_resolution(signals)

        # Step 4: Periodic health recalculation
        if new_faults or self._should_recalculate_health():
            await self._recalculate_health(signals)

        return new_faults

    async def _check_fault_resolution(self, signals: Dict[str, Any]) -> None:
        """Check if any active faults should be resolved."""
        active_faults = self._fault_engine.get_active_faults()

        for fault in active_faults:
            # Find the rule for this fault
            for rule in self._fault_engine._rules:
                if rule.rule_id == fault.rule_id and rule.recovery_condition:
                    signal_name = rule.condition.signal if rule.condition else ""
                    if signal_name in signals:
                        value = float(signals[signal_name])
                        if rule.recovery_condition.evaluate(value):
                            # Resolve the fault
                            await self._fault_engine.resolve_fault(
                                rule.rule_id, reason="auto_recovery"
                            )
                            logger.info(
                                f"DiagnosticService: fault auto-resolved: {rule.rule_id}"
                            )

    async def _recalculate_health(self, signals: Dict[str, Any]) -> None:
        """Recalculate health scores."""
        # Build a minimal VehicleState for calculation
        state = VehicleState()
        state.engine.rpm = int(signals.get("rpm", 0))
        state.engine.coolant_temp = float(signals.get("temp", 25))
        state.engine.load = float(signals.get("engine_load", 0))
        state.engine.throttle_pos = float(signals.get("accelerator", 0))
        state.battery.voltage = float(signals.get("battery", 12.6))
        state.body.speed = float(signals.get("speed", 0))
        state.fuel.level = float(signals.get("fuel", 100))
        state.brakes.applied = bool(int(signals.get("brake", 0)))

        # Get active faults
        active_faults = self._fault_engine.get_active_faults()

        # Calculate
        self._last_health = self._health_calculator.calculate(state, [
            {
                "subsystem": f.subsystem,
                "severity": f.severity,
                "confidence": f.confidence,
            }
            for f in active_faults
        ])
        self._last_health_time = time.time()

        # Emit health update
        await self._event_bus.publish(
            EventType.HEALTH_UPDATED,
            data=self._last_health.to_dict(),
            source="diagnostic_service",
        )

    def _should_recalculate_health(self) -> bool:
        """Check if health needs recalculation (TTL-based)."""
        return (time.time() - self._last_health_time) > self._health_cache_ttl

    # ========================================================================
    # FAULT QUERIES
    # ========================================================================

    def get_active_faults(self) -> List[FaultEvent]:
        """Get all currently active faults."""
        return self._fault_engine.get_active_faults()

    def get_fault_history(self, limit: int = 100) -> List[FaultEvent]:
        """Get fault history."""
        return self._fault_engine.get_fault_history(limit=limit)

    async def acknowledge_fault(self, fault_id: str) -> bool:
        """Acknowledge a fault."""
        return self._fault_engine.acknowledge_fault(fault_id)

    async def resolve_fault(self, fault_id: str, reason: str = "manual") -> bool:
        """Manually resolve a fault."""
        # Find fault by ID
        for rule_id, fault in self._fault_engine._active_faults.items():
            if fault.fault_id == fault_id:
                await self._fault_engine.resolve_fault(rule_id, reason)
                return True
        return False

    # ========================================================================
    # HEALTH QUERIES
    # ========================================================================

    def get_health_scores(self) -> Optional[HealthScore]:
        """Get the most recent health scores."""
        return self._last_health

    def get_health_trend(self, subsystem: str) -> str:
        """Get health trend for a subsystem."""
        return self._health_calculator.get_trend(subsystem)

    # ========================================================================
    # TIMELINE QUERIES
    # ========================================================================

    def get_timeline(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent timeline entries."""
        entries = self._fault_engine._timeline.get_recent(limit=limit)
        return [e.to_dict() for e in entries]

    def log_timeline_event(
        self,
        event_type: str,
        message: str,
        severity: str = "INFO",
        **kwargs,
    ) -> None:
        """Log a custom timeline event."""
        self._fault_engine._timeline.log_event(
            event_type=event_type,
            message=message,
            severity=severity,
            **kwargs,
        )

    # ========================================================================
    # RECOMMENDATIONS
    # ========================================================================

    def get_recommendations(self) -> List[RepairRecommendation]:
        """Get repair recommendations for all active faults."""
        active_faults = self._fault_engine.get_active_faults()
        return self._recommendation_engine.get_recommendations_batch(active_faults)

    def get_recommendation_for_fault(self, fault_id: str) -> Optional[RepairRecommendation]:
        """Get recommendation for a specific fault."""
        for fault in self._fault_engine.get_active_faults():
            if fault.fault_id == fault_id:
                return self._recommendation_engine.get_recommendation(fault)
        return None

    # ========================================================================
    # RULE MANAGEMENT
    # ========================================================================

    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all fault rules."""
        return [rule.to_dict() for rule in self._fault_engine._rules]

    def toggle_rule(self, rule_id: str) -> Optional[bool]:
        """Toggle a rule's enabled state. Returns new state."""
        for rule in self._fault_engine._rules:
            if rule.rule_id == rule_id:
                rule.enabled = not rule.enabled
                return rule.enabled
        return None

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        return {
            "processing_count": self._processing_count,
            "total_faults_detected": self._total_faults_detected,
            "active_faults": self._fault_engine.active_fault_count,
            "last_health_score": self._last_health.overall if self._last_health else None,
            "last_health_time": self._last_health_time,
            "fault_engine_stats": self._fault_engine.get_stats(),
            "health_calculator_stats": self._health_calculator.get_stats(),
        }