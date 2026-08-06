"""
============================================================================
AutoTwin AI - Fault Timeline
============================================================================
Chronological logging of all diagnostic events.

Stores:
  - Fault detections
  - Fault resolutions
  - Threshold warnings
  - System events (CAN timeout, reconnection)
  - Scenario events

The timeline provides a complete audit trail for:
  - Post-event analysis
  - Diagnostic correlation
  - Service report generation
  - Replay context

Usage:
    timeline = FaultTimeline(event_bus)
    timeline.log_fault(fault_event)
    timeline.log_event("threshold_exceeded", "Coolant reached 110°C")
    recent = timeline.get_recent(limit=50)
============================================================================
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.constants import EventType, Severity
from app.core.event_bus import EventBus


# ============================================================================
# TIMELINE ENTRY
# ============================================================================


@dataclass
class TimelineEntry:
    """A single timeline event."""

    entry_id: str = ""
    timestamp: float = field(default_factory=time.time)
    event_type: str = "info"  # fault_detected, fault_resolved, warning, info, scenario
    severity: str = Severity.INFO.value
    message: str = ""
    signal_name: str = ""
    signal_value: float = 0.0
    subsystem: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # For fault events
    fault_id: str = ""
    rule_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "signal_name": self.signal_name,
            "signal_value": self.signal_value,
            "subsystem": self.subsystem,
            "fault_id": self.fault_id,
            "rule_id": self.rule_id,
            "metadata": self.metadata,
        }


# ============================================================================
# FAULT TIMELINE
# ============================================================================


class FaultTimeline:
    """
    Chronological event log for all diagnostic activity.

    Features:
      - Ring buffer with configurable capacity
      - Severity filtering
      - Time-range queries
      - Export for reports
      - Event bus integration
    """

    def __init__(self, event_bus: Optional[EventBus] = None, max_events: int = 10000):
        self._event_bus = event_bus
        self._entries: deque = deque(maxlen=max_events)
        self._max_events = max_events
        self._sequence: int = 0
        self._fault_count: int = 0
        self._warning_count: int = 0

    # ========================================================================
    # LOGGING METHODS
    # ========================================================================

    def log_fault(self, fault) -> TimelineEntry:
        """Log a fault detection event."""
        self._sequence += 1
        entry = TimelineEntry(
            entry_id=f"TE-{self._sequence:06d}",
            event_type="fault_detected",
            severity=fault.severity,
            message=fault.message,
            subsystem=fault.subsystem,
            fault_id=fault.fault_id,
            rule_id=fault.rule_id,
            signal_values=fault.signal_values,
            metadata={
                "confidence": fault.confidence,
                "possible_causes": fault.possible_causes[:3],
            },
        )
        self._entries.append(entry)
        self._fault_count += 1

        logger.debug(f"Timeline: fault logged: {fault.rule_id}")
        return entry

    def log_resolution(self, fault) -> TimelineEntry:
        """Log a fault resolution event."""
        self._sequence += 1
        entry = TimelineEntry(
            entry_id=f"TE-{self._sequence:06d}",
            event_type="fault_resolved",
            severity=Severity.INFO.value,
            message=f"Fault resolved: {fault.message}",
            subsystem=fault.subsystem,
            fault_id=fault.fault_id,
            rule_id=fault.rule_id,
            metadata={
                "duration_s": fault.duration_s,
                "resolution": fault.resolution_reason,
            },
        )
        self._entries.append(entry)
        return entry

    def log_event(
        self,
        event_type: str,
        message: str,
        severity: str = Severity.INFO.value,
        signal_name: str = "",
        signal_value: float = 0.0,
        subsystem: str = "",
        metadata: Optional[Dict] = None,
    ) -> TimelineEntry:
        """Log a generic timeline event."""
        self._sequence += 1
        entry = TimelineEntry(
            entry_id=f"TE-{self._sequence:06d}",
            event_type=event_type,
            severity=severity,
            message=message,
            signal_name=signal_name,
            signal_value=signal_value,
            subsystem=subsystem,
            metadata=metadata or {},
        )
        self._entries.append(entry)

        if severity in (Severity.HIGH.value, Severity.CRITICAL.value):
            self._warning_count += 1

        return entry

    def log_threshold_warning(
        self,
        signal_name: str,
        value: float,
        threshold: float,
        subsystem: str = "",
    ) -> TimelineEntry:
        """Log a threshold warning."""
        direction = "exceeded" if value > threshold else "below"
        message = f"{signal_name} {direction} threshold: {value:.1f} (limit: {threshold:.1f})"

        return self.log_event(
            event_type="threshold_warning",
            message=message,
            severity=Severity.MEDIUM.value,
            signal_name=signal_name,
            signal_value=value,
            subsystem=subsystem,
            metadata={"threshold": threshold},
        )

    def log_system_event(self, message: str, severity: str = Severity.INFO.value) -> TimelineEntry:
        """Log a system event (connection, timeout, etc.)."""
        return self.log_event(
            event_type="system",
            message=message,
            severity=severity,
        )

    # ========================================================================
    # QUERY METHODS
    # ========================================================================

    def get_recent(self, limit: int = 50) -> List[TimelineEntry]:
        """Get most recent entries (newest first)."""
        entries = list(self._entries)
        return entries[-limit:][::-1]

    def get_between(self, start_time: float, end_time: float) -> List[TimelineEntry]:
        """Get entries within a time range."""
        return [
            e for e in self._entries
            if start_time <= e.timestamp <= end_time
        ]

    def get_by_severity(self, severity: str, limit: int = 100) -> List[TimelineEntry]:
        """Get entries filtered by severity."""
        results = [e for e in self._entries if e.severity == severity]
        return results[-limit:]

    def get_by_type(self, event_type: str, limit: int = 100) -> List[TimelineEntry]:
        """Get entries filtered by event type."""
        results = [e for e in self._entries if e.event_type == event_type]
        return results[-limit:]

    def get_faults_only(self, limit: int = 100) -> List[TimelineEntry]:
        """Get only fault-related entries."""
        results = [
            e for e in self._entries
            if e.event_type in ("fault_detected", "fault_resolved")
        ]
        return results[-limit:]

    # ========================================================================
    # EXPORT
    # ========================================================================

    def export_to_list(self) -> List[Dict[str, Any]]:
        """Export all entries as serializable dictionaries."""
        return [e.to_dict() for e in self._entries]

    def clear(self) -> int:
        """Clear all timeline entries."""
        count = len(self._entries)
        self._entries.clear()
        return count

    # ========================================================================
    # STATISTICS
    # ========================================================================

    @property
    def size(self) -> int:
        return len(self._entries)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_entries": len(self._entries),
            "fault_count": self._fault_count,
            "warning_count": self._warning_count,
            "max_capacity": self._max_events,
            "sequence": self._sequence,
        }