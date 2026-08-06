"""
============================================================================
AutoTwin AI - Diagnostic Health Service
============================================================================
Bridges the HealthCalculator with the diagnostic pipeline.
Provides a service-level interface for health score computation
with fault integration and event emission.
============================================================================
"""

import time
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.constants import EventType
from app.core.event_bus import EventBus
from app.vehicle.vehicle_state import VehicleState
from app.vehicle.health_calculator import HealthCalculator, HealthScore
from app.diagnostics.fault_engine import FaultEvent


# ============================================================================
# DIAGNOSTIC HEALTH SERVICE
# ============================================================================


class DiagnosticHealthService:
    """
    Service-level health score computation.

    Combines:
      - VehicleState signal analysis
      - Active fault penalties
      - Historical trend tracking
      - Event emission for WebSocket broadcast

    Usage:
        service = DiagnosticHealthService(event_bus)
        score = service.compute(vehicle_state, active_faults)
    """

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._calculator = HealthCalculator(event_bus)
        self._last_score: Optional[HealthScore] = None
        self._last_compute_time: float = 0.0
        self._compute_interval_s: float = 2.0  # Minimum interval between computations

    async def compute(
        self,
        state: VehicleState,
        active_faults: Optional[List[FaultEvent]] = None,
        force: bool = False,
    ) -> HealthScore:
        """
        Compute health score from vehicle state and active faults.

        Args:
            state: Current vehicle state
            active_faults: List of active FaultEvent objects
            force: Bypass interval limiting

        Returns:
            HealthScore result
        """
        # Rate limiting
        now = time.time()
        if not force and (now - self._last_compute_time) < self._compute_interval_s:
            if self._last_score:
                return self._last_score

        # Convert FaultEvent objects to dictionaries for calculator
        fault_dicts = []
        if active_faults:
            for fault in active_faults:
                fault_dicts.append({
                    "subsystem": fault.subsystem,
                    "severity": fault.severity,
                    "confidence": fault.confidence,
                    "rule_id": fault.rule_id,
                })

        # Calculate
        score = self._calculator.calculate(state, fault_dicts)

        # Update state
        state.overall_health = score.overall
        state.active_fault_count = len(active_faults) if active_faults else 0

        # Emit event if significant change
        if self._last_score and abs(score.overall - self._last_score.overall) > 1.0:
            await self._event_bus.publish(
                EventType.HEALTH_UPDATED,
                data=score.to_dict(),
                source="health_service",
            )

        self._last_score = score
        self._last_compute_time = now

        return score

    def get_last_score(self) -> Optional[HealthScore]:
        """Get the most recent health score."""
        return self._last_score

    def get_trend(self, subsystem: str) -> str:
        """Get health trend for a subsystem."""
        return self._calculator.get_trend(subsystem)

    def get_history(self, limit: int = 100) -> List[HealthScore]:
        """Get health score history."""
        return self._calculator.get_history(limit)

    def get_stats(self) -> Dict[str, Any]:
        return self._calculator.get_stats()