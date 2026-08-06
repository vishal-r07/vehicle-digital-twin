"""
============================================================================
AutoTwin AI - Fault Detection Engine
============================================================================
Evaluates fault rules against live vehicle state.

Pipeline:
  StateChangedEvent → FaultEngine.evaluate()
    → For each applicable rule:
      → Check condition
      → Apply debounce/cooldown
      → If triggered: create FaultEvent
      → Emit FAULT_DETECTED event
      → Log to timeline
      → Update health score

Features:
  - Rule-based evaluation (deterministic)
  - Debounce (consecutive trigger requirement)
  - Duration (must persist for N ms)
  - Cooldown (prevent rapid re-trigger)
  - Auto-resolution (when condition clears)
  - Severity-weighted confidence
============================================================================
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from loguru import logger

from app.core.constants import EventType, Severity, Subsystem
from app.core.event_bus import Event, EventBus
from app.diagnostics.fault_rules import FaultRule, RuleLoader
from app.diagnostics.fault_timeline import FaultTimeline


# ============================================================================
# FAULT EVENT DATA STRUCTURE
# ============================================================================


@dataclass
class FaultEvent:
    """
    A detected fault event.

    Created when a fault rule triggers. Stored in timeline.
    Broadcast to frontend via WebSocket.
    """

    # Identity
    fault_id: str = field(default_factory=lambda: f"F-{uuid.uuid4().hex[:8].upper()}")
    rule_id: str = ""
    timestamp: float = field(default_factory=time.time)

    # Classification
    severity: str = Severity.MEDIUM.value
    confidence: float = 0.8
    priority: int = 3
    subsystem: str = Subsystem.ENGINE.value

    # Description
    message: str = ""
    signal_values: Dict[str, float] = field(default_factory=dict)

    # Diagnosis
    possible_causes: List[str] = field(default_factory=list)
    recommendation: str = ""
    estimated_repair_time: str = ""
    related_dtcs: List[str] = field(default_factory=list)

    # Status
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: float = 0.0
    resolution_reason: str = ""

    # Duration
    @property
    def duration_s(self) -> float:
        if self.resolved:
            return self.resolved_at - self.timestamp
        return time.time() - self.timestamp

    @property
    def is_active(self) -> bool:
        return not self.resolved

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fault_id": self.fault_id,
            "rule_id": self.rule_id,
            "timestamp": self.timestamp,
            "severity": self.severity,
            "confidence": self.confidence,
            "priority": self.priority,
            "subsystem": self.subsystem,
            "message": self.message,
            "signal_values": self.signal_values,
            "possible_causes": self.possible_causes,
            "recommendation": self.recommendation,
            "estimated_repair_time": self.estimated_repair_time,
            "related_dtcs": self.related_dtcs,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved,
            "duration_s": round(self.duration_s, 1),
        }


# ============================================================================
# FAULT ENGINE
# ============================================================================


class FaultEngine:
    """
    Evaluates fault rules against vehicle state.

    Subscribes to STATE_CHANGED events and evaluates applicable rules.
    Emits FAULT_DETECTED / FAULT_RESOLVED events.
    """

    def __init__(self, event_bus: EventBus, settings=None):
        self._event_bus = event_bus
        self._settings = settings

        # Rules
        self._rules: List[FaultRule] = []
        self._rules_by_signal: Dict[str, List[FaultRule]] = {}

        # Active faults
        self._active_faults: Dict[str, FaultEvent] = {}
        self._fault_history: List[FaultEvent] = []
        self._max_history: int = 500

        # Timeline
        self._timeline = FaultTimeline(event_bus)

        # Statistics
        self._total_evaluations: int = 0
        self._total_faults_detected: int = 0
        self._total_faults_resolved: int = 0

        # Subscription
        self._subscription = None

        logger.info("FaultEngine: initialized")

    # ========================================================================
    # LIFECYCLE
    # ========================================================================

    async def start(self) -> None:
        """Start the fault engine (subscribe to events)."""
        self._subscription = self._event_bus.subscribe(
            EventType.STATE_CHANGED,
            self._on_state_changed,
            priority=10,
        )
        logger.info("FaultEngine: started (subscribed to state changes)")

    async def stop(self) -> None:
        """Stop the fault engine."""
        if self._subscription:
            self._event_bus.unsubscribe(self._subscription)
        logger.info("FaultEngine: stopped")

    # ========================================================================
    # RULE MANAGEMENT
    # ========================================================================

    def load_rules(self, rules: List[FaultRule]) -> None:
        """Load fault rules and build signal index."""
        self._rules = rules
        self._rules_by_signal.clear()

        for rule in rules:
            if rule.condition:
                signal = rule.condition.signal
                if signal not in self._rules_by_signal:
                    self._rules_by_signal[signal] = []
                self._rules_by_signal[signal].append(rule)

        logger.info(f"FaultEngine: loaded {len(rules)} rules ({len(self._rules_by_signal)} signals)")

    def load_rules_from_file(self, path: str) -> int:
        """Load rules from a YAML file."""
        loader = RuleLoader(path)
        rules = loader.load()
        self.load_rules(rules)
        return len(rules)

    def enable_rule(self, rule_id: str) -> bool:
        """Enable a specific rule."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.enabled = True
                return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable a specific rule."""
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.enabled = False
                return True
        return False

    # ========================================================================
    # EVALUATION
    # ========================================================================

    async def _on_state_changed(self, event: Event) -> None:
        """Handle state change event — evaluate applicable rules."""
        data = event.data
        if not data:
            return

        signal_name = data.get("signal")
        value = data.get("value")
        prev_value = data.get("previous", 0)

        if signal_name is None or value is None:
            return

        # Get rules for this signal
        applicable_rules = self._rules_by_signal.get(signal_name, [])
        if not applicable_rules:
            return

        # Evaluate each rule
        for rule in applicable_rules:
            self._total_evaluations += 1

            try:
                triggered = rule.evaluate(
                    signal_value=float(value),
                    prev_value=float(prev_value) if prev_value else 0.0,
                    dt_s=0.05,  # Approximate 20Hz
                )

                if triggered and not rule.rule_id in self._active_faults:
                    # New fault detected
                    await self._trigger_fault(rule, signal_name, float(value))

            except Exception as e:
                logger.error(f"FaultEngine: rule '{rule.rule_id}' evaluation error: {e}")

    def evaluate_state(self, signals: Dict[str, float]) -> List[FaultEvent]:
        """
        Evaluate all rules against a complete signal dictionary.
        Used for batch evaluation (scenario/replay mode).

        Args:
            signals: Dictionary of {signal_name: value}

        Returns:
            List of newly triggered FaultEvents.
        """
        new_faults = []

        for rule in self._rules:
            if not rule.enabled or not rule.condition:
                continue

            signal_name = rule.condition.signal
            if signal_name not in signals:
                continue

            value = signals[signal_name]
            self._total_evaluations += 1

            try:
                triggered = rule.evaluate(signal_value=float(value))

                if triggered and rule.rule_id not in self._active_faults:
                    fault = self._create_fault_event(rule, signal_name, float(value))
                    self._active_faults[rule.rule_id] = fault
                    new_faults.append(fault)

            except Exception as e:
                logger.error(f"FaultEngine: evaluation error: {e}")

        return new_faults

    async def _trigger_fault(self, rule: FaultRule, signal: str, value: float) -> None:
        """Handle a newly triggered fault."""
        fault = self._create_fault_event(rule, signal, value)
        self._active_faults[rule.rule_id] = fault
        self._fault_history.append(fault)
        self._total_faults_detected += 1

        # Trim history
        if len(self._fault_history) > self._max_history:
            self._fault_history.pop(0)

        # Log to timeline
        self._timeline.log_fault(fault)

        # Emit event
        await self._event_bus.publish(
            EventType.FAULT_DETECTED,
            data=fault.to_dict(),
            source="fault_engine",
            priority=5,
        )

        logger.warning(
            f"FaultEngine: FAULT DETECTED [{fault.severity}] "
            f"{rule.rule_id}: {fault.message}"
        )

    def _create_fault_event(self, rule: FaultRule, signal: str, value: float) -> FaultEvent:
        """Create a FaultEvent from a triggered rule."""
        return FaultEvent(
            rule_id=rule.rule_id,
            severity=rule.severity,
            confidence=rule.confidence,
            priority=rule.priority,
            subsystem=rule.subsystem,
            message=f"{rule.name}: {rule.description}",
            signal_values={signal: value},
            possible_causes=rule.possible_causes,
            recommendation=rule.recommendation,
            estimated_repair_time=rule.estimated_repair_time,
            related_dtcs=rule.related_dtcs,
        )

    # ========================================================================
    # FAULT RESOLUTION
    # ========================================================================

    async def resolve_fault(self, rule_id: str, reason: str = "auto") -> Optional[FaultEvent]:
        """Resolve an active fault."""
        if rule_id not in self._active_faults:
            return None

        fault = self._active_faults.pop(rule_id)
        fault.resolved = True
        fault.resolved_at = time.time()
        fault.resolution_reason = reason
        self._total_faults_resolved += 1

        # Reset rule state
        for rule in self._rules:
            if rule.rule_id == rule_id:
                rule.reset()
                break

        # Log to timeline
        self._timeline.log_resolution(fault)

        # Emit event
        await self._event_bus.publish(
            EventType.FAULT_RESOLVED,
            data={
                "fault_id": fault.fault_id,
                "rule_id": rule_id,
                "resolution": reason,
                "duration_s": fault.duration_s,
            },
            source="fault_engine",
        )

        logger.info(f"FaultEngine: fault resolved: {rule_id} ({reason})")
        return fault

    def acknowledge_fault(self, fault_id: str) -> bool:
        """Mark a fault as acknowledged by technician."""
        for fault in self._active_faults.values():
            if fault.fault_id == fault_id:
                fault.acknowledged = True
                return True
        return False

    # ========================================================================
    # QUERIES
    # ========================================================================

    def get_active_faults(self) -> List[FaultEvent]:
        """Get all currently active faults."""
        return list(self._active_faults.values())

    def get_fault_history(self, limit: int = 100) -> List[FaultEvent]:
        """Get recent fault history."""
        return self._fault_history[-limit:]

    def get_faults_by_severity(self, severity: str) -> List[FaultEvent]:
        """Get active faults filtered by severity."""
        return [f for f in self._active_faults.values() if f.severity == severity]

    def get_faults_by_subsystem(self, subsystem: str) -> List[FaultEvent]:
        """Get active faults for a subsystem."""
        return [f for f in self._active_faults.values() if f.subsystem == subsystem]

    @property
    def active_fault_count(self) -> int:
        return len(self._active_faults)

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        return {
            "rules_loaded": len(self._rules),
            "rules_enabled": sum(1 for r in self._rules if r.enabled),
            "active_faults": len(self._active_faults),
            "total_evaluations": self._total_evaluations,
            "total_faults_detected": self._total_faults_detected,
            "total_faults_resolved": self._total_faults_resolved,
            "fault_history_size": len(self._fault_history),
        }