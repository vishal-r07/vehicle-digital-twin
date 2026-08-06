"""
============================================================================
AutoTwin AI - Diagnostic API Schemas
============================================================================
Pydantic models for diagnostics, health, and timeline endpoints.

Schemas:
  - FaultEventSchema:       Single fault event
  - FaultListResponse:      List of faults
  - FaultDetailResponse:    Fault with recommendation
  - HealthScoreSchema:      Health score breakdown
  - HealthResponse:         Health endpoint response
  - TimelineEntrySchema:    Single timeline event
  - TimelineResponse:       Timeline list response
  - FaultRuleSchema:        Fault rule definition
  - RecommendationSchema:   Repair recommendation
============================================================================
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.constants import Severity


# ============================================================================
# FAULT EVENT SCHEMAS
# ============================================================================


class FaultEventSchema(BaseModel):
    """A single fault event."""

    fault_id: str = Field(..., description="Unique fault identifier")
    rule_id: str = Field(..., description="Rule that triggered this fault")
    timestamp: float = Field(..., description="Unix timestamp of detection")
    severity: str = Field(..., description="INFO, LOW, MEDIUM, HIGH, CRITICAL")
    confidence: float = Field(0.8, ge=0.0, le=1.0, description="Detection confidence")
    priority: int = Field(3, ge=1, le=5, description="1=critical, 5=info")
    subsystem: str = Field(..., description="Affected subsystem")
    message: str = Field(..., description="Human-readable fault description")

    # Signal context
    signal_values: Dict[str, float] = Field(
        default_factory=dict,
        description="Signal values at time of detection",
    )

    # Diagnosis
    possible_causes: List[str] = Field(default_factory=list)
    recommendation: str = ""
    estimated_repair_time: str = ""
    related_dtcs: List[str] = Field(default_factory=list)

    # Status
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[float] = None
    duration_s: float = Field(0.0, description="Duration in seconds")

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v):
        valid = {s.value for s in Severity}
        if v.upper() not in valid:
            raise ValueError(f"Invalid severity: {v}. Must be one of {valid}")
        return v.upper()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "fault_id": "F-A1B2C3D4",
                    "rule_id": "COOLANT_OVERHEAT",
                    "timestamp": 1705312200.123,
                    "severity": "HIGH",
                    "confidence": 0.85,
                    "priority": 2,
                    "subsystem": "cooling",
                    "message": "Engine Overheat: Coolant temperature exceeds safe threshold",
                    "signal_values": {"temp": 112.0},
                    "possible_causes": [
                        "Thermostat stuck closed",
                        "Low coolant level",
                        "Radiator fan failure",
                    ],
                    "recommendation": "Stop engine. Check coolant level.",
                    "estimated_repair_time": "1-3 hours",
                    "related_dtcs": ["P0217"],
                    "acknowledged": False,
                    "resolved": False,
                    "duration_s": 45.2,
                }
            ]
        }
    }


class FaultListResponse(BaseModel):
    """Response for listing faults."""

    success: bool = True
    data: "FaultListData"
    meta: Dict[str, Any] = Field(default_factory=dict)


class FaultListData(BaseModel):
    faults: List[FaultEventSchema] = Field(default_factory=list)
    count: int = 0
    total_active: int = 0


class FaultDetailResponse(BaseModel):
    """Response for fault details with recommendation."""

    success: bool = True
    data: "FaultDetailData"


class FaultDetailData(BaseModel):
    fault: FaultEventSchema
    recommendation: Optional["RecommendationSchema"] = None


# ============================================================================
# FAULT RULE SCHEMAS
# ============================================================================


class RuleConditionSchema(BaseModel):
    """Fault rule condition definition."""

    signal: str
    operator: str = Field(..., description=">, <, >=, <=, ==, !=, between, change, rate")
    threshold: float = 0.0
    threshold_high: float = 0.0
    duration_ms: int = 0
    debounce_count: int = 1


class FaultRuleSchema(BaseModel):
    """Fault detection rule definition."""

    rule_id: str
    name: str
    description: str = ""
    subsystem: str
    severity: str
    priority: int = 3
    enabled: bool = True
    is_active: bool = False
    trigger_count: int = 0
    condition: Optional[RuleConditionSchema] = None
    possible_causes: List[str] = Field(default_factory=list)
    recommendation: str = ""
    estimated_repair_time: str = ""
    cooldown_s: float = 30.0


class FaultRuleListResponse(BaseModel):
    """Response for listing fault rules."""

    success: bool = True
    data: "FaultRuleListData"


class FaultRuleListData(BaseModel):
    rules: List[FaultRuleSchema] = Field(default_factory=list)
    count: int = 0
    enabled_count: int = 0


# ============================================================================
# HEALTH SCORE SCHEMAS
# ============================================================================


class SubsystemHealthSchema(BaseModel):
    """Health score for a single subsystem."""

    name: str
    score: float = Field(100.0, ge=0.0, le=100.0)
    status: str = Field("good", description="good, warning, poor, critical")
    trend: str = Field("stable", description="improving, stable, declining")
    active_faults: int = 0


class HealthScoreSchema(BaseModel):
    """Complete health score breakdown."""

    overall: float = Field(100.0, ge=0.0, le=100.0)
    engine: float = Field(100.0, ge=0.0, le=100.0)
    transmission: float = Field(100.0, ge=0.0, le=100.0)
    brakes: float = Field(100.0, ge=0.0, le=100.0)
    cooling: float = Field(100.0, ge=0.0, le=100.0)
    battery: float = Field(100.0, ge=0.0, le=100.0)
    electrical: float = Field(100.0, ge=0.0, le=100.0)
    fuel: float = Field(100.0, ge=0.0, le=100.0)

    status: str = Field("good", description="Overall status")
    active_fault_count: int = 0
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())

    subsystems: Dict[str, SubsystemHealthSchema] = Field(default_factory=dict)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "overall": 78.5,
                    "engine": 82.0,
                    "transmission": 95.0,
                    "brakes": 90.0,
                    "cooling": 62.0,
                    "battery": 88.0,
                    "electrical": 92.0,
                    "fuel": 98.0,
                    "status": "warning",
                    "active_fault_count": 1,
                }
            ]
        }
    }


class HealthResponse(BaseModel):
    """Response for health score endpoint."""

    success: bool = True
    data: HealthScoreSchema


class HealthHistoryResponse(BaseModel):
    """Response for health history endpoint."""

    success: bool = True
    data: "HealthHistoryData"


class HealthHistoryData(BaseModel):
    snapshots: List[HealthScoreSchema] = Field(default_factory=list)
    count: int = 0


class HealthTrendResponse(BaseModel):
    """Response for health trends endpoint."""

    success: bool = True
    data: "HealthTrendData"


class HealthTrendData(BaseModel):
    trends: Dict[str, str] = Field(
        default_factory=dict,
        description="Subsystem → trend (improving/stable/declining)",
    )


class HealthSummaryResponse(BaseModel):
    """Quick health summary for status displays."""

    success: bool = True
    data: "HealthSummaryData"


class HealthSummaryData(BaseModel):
    overall_score: float
    status: str
    active_faults: int
    can_active: bool


# ============================================================================
# TIMELINE SCHEMAS
# ============================================================================


class TimelineEntrySchema(BaseModel):
    """A single timeline event."""

    entry_id: str
    timestamp: float
    event_type: str = Field(
        ...,
        description="fault_detected, fault_resolved, threshold_warning, system, scenario",
    )
    severity: str = "INFO"
    message: str
    signal_name: str = ""
    signal_value: float = 0.0
    subsystem: str = ""
    fault_id: str = ""
    rule_id: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    """Response for timeline endpoint."""

    success: bool = True
    data: "TimelineData"


class TimelineData(BaseModel):
    events: List[TimelineEntrySchema] = Field(default_factory=list)
    count: int = 0
    total_entries: int = 0


# ============================================================================
# RECOMMENDATION SCHEMAS
# ============================================================================


class RecommendationSchema(BaseModel):
    """Repair recommendation for a fault."""

    fault_id: str = ""
    rule_id: str = ""
    subsystem: str = ""
    severity: str = ""

    # Diagnosis
    possible_causes: List[str] = Field(default_factory=list)
    most_likely_cause: str = ""
    confidence: float = 0.8

    # Action
    immediate_action: str = ""
    inspection_steps: List[str] = Field(default_factory=list)
    recommended_repair: str = ""

    # Estimates
    estimated_time: str = ""
    estimated_cost_range: str = ""
    priority: int = 3

    # References
    related_dtcs: List[str] = Field(default_factory=list)

    # Urgency
    is_drivable: bool = True
    requires_immediate_stop: bool = False


class RecommendationListResponse(BaseModel):
    """Response for recommendations endpoint."""

    success: bool = True
    data: "RecommendationListData"


class RecommendationListData(BaseModel):
    recommendations: List[RecommendationSchema] = Field(default_factory=list)
    count: int = 0


# ============================================================================
# ACKNOWLEDGE REQUEST
# ============================================================================


class FaultAcknowledgeRequest(BaseModel):
    """Request to acknowledge a fault."""

    notes: str = Field("", description="Optional technician notes")


class FaultAcknowledgeResponse(BaseModel):
    """Response after acknowledging a fault."""

    success: bool = True
    data: Dict[str, Any]


# ============================================================================
# RULE TOGGLE
# ============================================================================


class RuleToggleResponse(BaseModel):
    """Response after toggling a rule."""

    success: bool = True
    data: "RuleToggleData"


class RuleToggleData(BaseModel):
    rule_id: str
    enabled: bool
    message: str


# Update forward references
FaultListResponse.model_rebuild()
FaultDetailResponse.model_rebuild()
FaultRuleListResponse.model_rebuild()
HealthHistoryResponse.model_rebuild()
HealthTrendResponse.model_rebuild()
HealthSummaryResponse.model_rebuild()
TimelineResponse.model_rebuild()
RecommendationListResponse.model_rebuild()
RuleToggleResponse.model_rebuild()