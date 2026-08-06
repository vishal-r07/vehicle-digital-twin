"""
============================================================================
AutoTwin AI - Repair Recommendations Engine
============================================================================
Generates actionable repair recommendations based on detected faults.

Each recommendation includes:
  - Possible causes (ranked by likelihood)
  - Recommended inspection steps
  - Estimated repair time
  - Priority level
  - Related DTCs
  - Cost estimate range (future)

Usage:
    engine = RecommendationEngine()
    rec = engine.get_recommendation(fault_event)
    # rec.possible_causes = ["Thermostat stuck closed", ...]
    # rec.inspection_steps = ["Check coolant level", ...]
    # rec.estimated_time = "1-3 hours"
============================================================================
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.constants import Severity, Subsystem
from app.diagnostics.fault_engine import FaultEvent


# ============================================================================
# RECOMMENDATION DATA STRUCTURE
# ============================================================================


@dataclass
class RepairRecommendation:
    """Complete repair recommendation for a fault."""

    fault_id: str = ""
    rule_id: str = ""
    subsystem: str = ""
    severity: str = Severity.MEDIUM.value

    # Diagnosis
    possible_causes: List[str] = field(default_factory=list)
    most_likely_cause: str = ""
    confidence: float = 0.8

    # Action
    immediate_action: str = ""
    inspection_steps: List[str] = field(default_factory=list)
    recommended_repair: str = ""

    # Estimates
    estimated_time: str = ""
    estimated_cost_range: str = ""
    priority: int = 3  # 1=immediate, 5=next service

    # References
    related_dtcs: List[str] = field(default_factory=list)
    service_bulletins: List[str] = field(default_factory=list)

    # Urgency
    is_drivable: bool = True
    requires_immediate_stop: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fault_id": self.fault_id,
            "rule_id": self.rule_id,
            "subsystem": self.subsystem,
            "severity": self.severity,
            "possible_causes": self.possible_causes,
            "most_likely_cause": self.most_likely_cause,
            "confidence": self.confidence,
            "immediate_action": self.immediate_action,
            "inspection_steps": self.inspection_steps,
            "recommended_repair": self.recommended_repair,
            "estimated_time": self.estimated_time,
            "estimated_cost_range": self.estimated_cost_range,
            "priority": self.priority,
            "related_dtcs": self.related_dtcs,
            "is_drivable": self.is_drivable,
            "requires_immediate_stop": self.requires_immediate_stop,
        }


# ============================================================================
# RECOMMENDATION ENGINE
# ============================================================================


class RecommendationEngine:
    """
    Generates repair recommendations from fault events.

    Uses a knowledge base of common repairs mapped to fault rules.
    Can be extended with vehicle-specific data.
    """

    # Knowledge base: rule_id → recommendation template
    KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {
        "COOLANT_OVERHEAT": {
            "immediate_action": "Reduce speed. Turn off A/C. If temp exceeds 120°C, stop engine.",
            "inspection_steps": [
                "Check coolant level in reservoir",
                "Inspect for visible coolant leaks",
                "Verify radiator fan operation",
                "Check thermostat operation",
                "Inspect water pump for leaks/noise",
                "Check radiator for blockage",
            ],
            "recommended_repair": "Replace thermostat. Top up coolant. Pressure test system.",
            "estimated_cost_range": "$150 - $500",
            "is_drivable": True,
            "requires_immediate_stop": False,
        },
        "CRITICAL_OVERHEAT": {
            "immediate_action": "STOP ENGINE IMMEDIATELY. Do not open radiator cap while hot.",
            "inspection_steps": [
                "Allow engine to cool completely (30+ minutes)",
                "Check coolant level",
                "Inspect for major leaks",
                "Check for head gasket failure (white smoke, milky oil)",
                "Pressure test cooling system",
            ],
            "recommended_repair": "Tow to service center. Full cooling system inspection.",
            "estimated_cost_range": "$500 - $3000",
            "is_drivable": False,
            "requires_immediate_stop": True,
        },
        "LOW_BATTERY_VOLTAGE": {
            "immediate_action": "Minimize electrical load. Avoid stopping engine.",
            "inspection_steps": [
                "Check battery terminal connections (clean, tight)",
                "Measure alternator output (should be 13.5-14.8V)",
                "Load test battery",
                "Check for parasitic drain",
                "Inspect drive belt condition",
            ],
            "recommended_repair": "Test/replace battery. Check alternator output.",
            "estimated_cost_range": "$100 - $600",
            "is_drivable": True,
            "requires_immediate_stop": False,
        },
        "RPM_REDLINE": {
            "immediate_action": "Reduce throttle immediately. Downshift if manual.",
            "inspection_steps": [
                "Check for transmission slipping",
                "Verify throttle position sensor",
                "Check engine governor/limiter",
            ],
            "recommended_repair": "Address driving behavior. Check transmission if persistent.",
            "estimated_cost_range": "$0 - $2000",
            "is_drivable": True,
            "requires_immediate_stop": False,
        },
        "LOW_FUEL": {
            "immediate_action": "Refuel at nearest station.",
            "inspection_steps": [
                "Refuel vehicle",
                "Check for fuel leaks if level drops rapidly",
            ],
            "recommended_repair": "Refuel. Avoid running tank below 1/4 regularly.",
            "estimated_cost_range": "$0",
            "is_drivable": True,
            "requires_immediate_stop": False,
        },
    }

    def __init__(self):
        self._recommendations_generated: int = 0

    def get_recommendation(self, fault: FaultEvent) -> RepairRecommendation:
        """
        Generate a repair recommendation for a fault event.

        Args:
            fault: The detected fault event

        Returns:
            RepairRecommendation with actionable guidance
        """
        # Look up knowledge base
        template = self.KNOWLEDGE_BASE.get(fault.rule_id, {})

        rec = RepairRecommendation(
            fault_id=fault.fault_id,
            rule_id=fault.rule_id,
            subsystem=fault.subsystem,
            severity=fault.severity,
            possible_causes=fault.possible_causes,
            most_likely_cause=fault.possible_causes[0] if fault.possible_causes else "Unknown",
            confidence=fault.confidence,
            immediate_action=template.get("immediate_action", fault.recommendation),
            inspection_steps=template.get("inspection_steps", []),
            recommended_repair=template.get("recommended_repair", fault.recommendation),
            estimated_time=fault.estimated_repair_time,
            estimated_cost_range=template.get("estimated_cost_range", "TBD"),
            priority=fault.priority,
            related_dtcs=fault.related_dtcs,
            is_drivable=template.get("is_drivable", True),
            requires_immediate_stop=template.get("requires_immediate_stop", False),
        )

        self._recommendations_generated += 1
        return rec

    def get_recommendations_batch(self, faults: List[FaultEvent]) -> List[RepairRecommendation]:
        """Generate recommendations for multiple faults."""
        return [self.get_recommendation(f) for f in faults]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "recommendations_generated": self._recommendations_generated,
            "knowledge_base_size": len(self.KNOWLEDGE_BASE),
        }