"""
============================================================================
AutoTwin AI - Diagnostics Module
============================================================================
Intelligent vehicle diagnostics:
  - FaultEngine: Evaluates rules against vehicle state
  - FaultRules: YAML-driven rule definitions
  - FaultTimeline: Chronological event logging
  - HealthScore: Aggregated health scoring
  - Recommendations: Repair suggestions

Pipeline:
  VehicleState → FaultEngine.evaluate() → FaultEvent
  FaultEvent → FaultTimeline.log() → TimelineEntry
  FaultEvent → Recommendations.suggest() → RepairAdvice
============================================================================
"""

from app.diagnostics.fault_engine import FaultEngine, FaultEvent  # noqa: F401
from app.diagnostics.fault_rules import (  # noqa: F401
    FaultRule,
    RuleCondition,
    RuleLoader,
)
from app.diagnostics.fault_timeline import FaultTimeline, TimelineEntry  # noqa: F401
from app.diagnostics.health_score import DiagnosticHealthService  # noqa: F401
from app.diagnostics.recommendations import (  # noqa: F401
    RecommendationEngine,
    RepairRecommendation,
)

__all__ = [
    "FaultEngine",
    "FaultEvent",
    "FaultRule",
    "RuleCondition",
    "RuleLoader",
    "FaultTimeline",
    "TimelineEntry",
    "DiagnosticHealthService",
    "RecommendationEngine",
    "RepairRecommendation",
]