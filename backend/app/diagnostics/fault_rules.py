"""
============================================================================
AutoTwin AI - Fault Rule Definitions
============================================================================
Defines the structure and loading of diagnostic fault rules.

Rules are defined in YAML per vehicle:
  vehicles/toyota_corolla_2020/fault_rules.yaml

Rule Structure:
  - id: Unique identifier
  - condition: Signal + operator + threshold
  - severity: INFO/LOW/MEDIUM/HIGH/CRITICAL
  - debounce: Persistence requirement
  - cooldown: Re-trigger prevention
  - diagnosis: Causes, recommendations, repair time

Usage:
    loader = RuleLoader("vehicles/toyota/fault_rules.yaml")
    rules = loader.load()
    engine = FaultEngine(rules)
============================================================================
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger

from app.core.constants import Severity, Subsystem


# ============================================================================
# RULE CONDITION
# ============================================================================


@dataclass
class RuleCondition:
    """
    A single condition within a fault rule.

    Evaluates: signal_value <operator> threshold
    """

    signal: str                   # Signal name to monitor
    operator: str                 # >, <, >=, <=, ==, !=, between, change, rate
    threshold: float = 0.0       # Primary threshold
    threshold_high: float = 0.0  # Upper threshold (for "between")
    duration_ms: int = 0         # Must persist for this long
    debounce_count: int = 1      # Must trigger N consecutive times
    window_ms: int = 100         # Window for rate calculations

    # Compound conditions
    and_conditions: List["RuleCondition"] = field(default_factory=list)
    or_conditions: List["RuleCondition"] = field(default_factory=list)

    def evaluate(self, value: float, prev_value: float = 0.0, dt_s: float = 1.0) -> bool:
        """
        Evaluate this condition against a signal value.

        Args:
            value: Current signal value
            prev_value: Previous signal value (for rate/change)
            dt_s: Time delta in seconds (for rate)

        Returns:
            True if condition is met.
        """
        # Check AND conditions first
        if self.and_conditions:
            if not all(c.evaluate(value, prev_value, dt_s) for c in self.and_conditions):
                return False

        # Check OR conditions
        if self.or_conditions:
            if not any(c.evaluate(value, prev_value, dt_s) for c in self.or_conditions):
                return False

        # Evaluate primary condition
        if self.operator == ">":
            return value > self.threshold
        elif self.operator == "<":
            return value < self.threshold
        elif self.operator == ">=":
            return value >= self.threshold
        elif self.operator == "<=":
            return value <= self.threshold
        elif self.operator == "==":
            return abs(value - self.threshold) < 0.001
        elif self.operator == "!=":
            return abs(value - self.threshold) >= 0.001
        elif self.operator == "between":
            return self.threshold <= value <= self.threshold_high
        elif self.operator == "not_between":
            return value < self.threshold or value > self.threshold_high
        elif self.operator == "change":
            return abs(value - prev_value) > self.threshold
        elif self.operator == "rate":
            if dt_s <= 0:
                return False
            rate = abs(value - prev_value) / dt_s
            return rate > self.threshold
        else:
            logger.warning(f"Unknown operator: {self.operator}")
            return False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleCondition":
        """Create condition from YAML dictionary."""
        and_conds = []
        or_conds = []

        if "AND" in data:
            and_data = data["AND"]
            if isinstance(and_data, dict):
                and_conds = [cls.from_dict(and_data)]
            elif isinstance(and_data, list):
                and_conds = [cls.from_dict(c) for c in and_data]

        if "OR" in data:
            or_data = data["OR"]
            if isinstance(or_data, dict):
                or_conds = [cls.from_dict(or_data)]
            elif isinstance(or_data, list):
                or_conds = [cls.from_dict(c) for c in or_data]

        return cls(
            signal=data.get("signal", ""),
            operator=data.get("operator", ">"),
            threshold=float(data.get("threshold", 0)),
            threshold_high=float(data.get("threshold_high", 0)),
            duration_ms=int(data.get("duration_ms", 0)),
            debounce_count=int(data.get("debounce_count", 1)),
            window_ms=int(data.get("window_ms", 100)),
            and_conditions=and_conds,
            or_conditions=or_conds,
        )


# ============================================================================
# FAULT RULE
# ============================================================================


@dataclass
class FaultRule:
    """
    Complete fault detection rule.

    A rule monitors a signal and triggers a fault when conditions are met.
    """

    # Identity
    rule_id: str
    name: str
    description: str = ""
    subsystem: str = Subsystem.ENGINE.value
    enabled: bool = True

    # Condition
    condition: Optional[RuleCondition] = None

    # Recovery condition (when fault clears)
    recovery_condition: Optional[RuleCondition] = None

    # Severity and priority
    severity: str = Severity.MEDIUM.value
    priority: int = 3  # 1=critical, 5=info

    # Timing
    cooldown_s: float = 30.0  # Seconds before re-trigger after resolution

    # Diagnosis
    possible_causes: List[str] = field(default_factory=list)
    confidence: float = 0.8
    recommendation: str = ""
    estimated_repair_time: str = ""
    related_dtcs: List[str] = field(default_factory=list)

    # Health impact
    health_score_impact: float = -10.0

    # Runtime state (not serialized)
    _trigger_count: int = field(default=0, repr=False)
    _consecutive_triggers: int = field(default=0, repr=False)
    _first_trigger_time: float = field(default=0.0, repr=False)
    _last_trigger_time: float = field(default=0.0, repr=False)
    _last_resolution_time: float = field(default=0.0, repr=False)
    _is_active: bool = field(default=False, repr=False)

    # ========================================================================
    # EVALUATION
    # ========================================================================

    def evaluate(
        self,
        signal_value: float,
        prev_value: float = 0.0,
        dt_s: float = 1.0,
    ) -> bool:
        """
        Evaluate this rule against current signal value.

        Handles debounce and duration requirements.

        Returns:
            True if fault should be triggered.
        """
        if not self.enabled or self.condition is None:
            return False

        # Check cooldown
        if self._last_resolution_time > 0:
            elapsed = time.time() - self._last_resolution_time
            if elapsed < self.cooldown_s:
                return False

        # Evaluate condition
        condition_met = self.condition.evaluate(signal_value, prev_value, dt_s)

        if condition_met:
            self._consecutive_triggers += 1

            # Track first trigger time for duration check
            if self._first_trigger_time == 0:
                self._first_trigger_time = time.time()

            # Check debounce count
            if self._consecutive_triggers < self.condition.debounce_count:
                return False

            # Check duration
            if self.condition.duration_ms > 0:
                elapsed_ms = (time.time() - self._first_trigger_time) * 1000
                if elapsed_ms < self.condition.duration_ms:
                    return False

            # All conditions met — trigger fault
            self._trigger_count += 1
            self._last_trigger_time = time.time()
            self._is_active = True
            return True
        else:
            # Reset consecutive counter
            self._consecutive_triggers = 0
            self._first_trigger_time = 0.0

            # Check recovery
            if self._is_active and self.recovery_condition:
                if self.recovery_condition.evaluate(signal_value, prev_value, dt_s):
                    self._is_active = False
                    self._last_resolution_time = time.time()

            return False

    def reset(self) -> None:
        """Reset runtime state."""
        self._consecutive_triggers = 0
        self._first_trigger_time = 0.0
        self._is_active = False

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def trigger_count(self) -> int:
        return self._trigger_count

    # ========================================================================
    # SERIALIZATION
    # ========================================================================

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FaultRule":
        """Create FaultRule from YAML dictionary."""
        condition = None
        if "condition" in data:
            condition = RuleCondition.from_dict(data["condition"])

        recovery = None
        if "recovery" in data:
            recovery = RuleCondition.from_dict(data["recovery"])

        diagnosis = data.get("diagnosis", {})

        return cls(
            rule_id=data.get("id", "UNKNOWN"),
            name=data.get("name", "Unknown Rule"),
            description=data.get("description", ""),
            subsystem=data.get("subsystem", Subsystem.ENGINE.value),
            enabled=data.get("enabled", True),
            condition=condition,
            recovery_condition=recovery,
            severity=data.get("severity", Severity.MEDIUM.value),
            priority=int(data.get("priority", 3)),
            cooldown_s=float(data.get("cooldown_s", 30.0)),
            possible_causes=diagnosis.get("possible_causes", []),
            confidence=float(diagnosis.get("confidence", 0.8)),
            recommendation=diagnosis.get("recommendation", ""),
            estimated_repair_time=diagnosis.get("estimated_repair_time", ""),
            related_dtcs=diagnosis.get("related_dtcs", []),
            health_score_impact=float(data.get("health_score_impact", -10.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "subsystem": self.subsystem,
            "severity": self.severity,
            "priority": self.priority,
            "enabled": self.enabled,
            "is_active": self._is_active,
            "trigger_count": self._trigger_count,
            "possible_causes": self.possible_causes,
            "recommendation": self.recommendation,
            "estimated_repair_time": self.estimated_repair_time,
        }


# ============================================================================
# RULE LOADER
# ============================================================================


class RuleLoader:
    """
    Loads fault rules from YAML files.

    Supports:
      - Single vehicle rule file
      - Default/fallback rules
      - Rule validation
    """

    def __init__(self, rules_path: Optional[str] = None):
        self._rules_path = rules_path
        self._rules: List[FaultRule] = []

    def load(self) -> List[FaultRule]:
        """Load rules from YAML file."""
        if not self._rules_path:
            logger.warning("RuleLoader: no rules path configured")
            return self._get_default_rules()

        path = Path(self._rules_path)
        if not path.exists():
            logger.warning(f"RuleLoader: file not found: {path}")
            return self._get_default_rules()

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "rules" not in data:
                logger.warning(f"RuleLoader: no 'rules' key in {path}")
                return self._get_default_rules()

            self._rules = []
            for rule_data in data["rules"]:
                try:
                    rule = FaultRule.from_dict(rule_data)
                    self._rules.append(rule)
                except Exception as e:
                    logger.error(f"RuleLoader: error parsing rule: {e}")

            logger.info(f"RuleLoader: loaded {len(self._rules)} rules from {path.name}")
            return self._rules

        except yaml.YAMLError as e:
            logger.error(f"RuleLoader: YAML parse error: {e}")
            return self._get_default_rules()

    def load_from_dict(self, data: Dict[str, Any]) -> List[FaultRule]:
        """Load rules from a dictionary (for testing)."""
        self._rules = []
        for rule_data in data.get("rules", []):
            rule = FaultRule.from_dict(rule_data)
            self._rules.append(rule)
        return self._rules

    def _get_default_rules(self) -> List[FaultRule]:
        """Get built-in default rules (used when no YAML file exists)."""
        return [
            FaultRule(
                rule_id="COOLANT_OVERHEAT",
                name="Engine Overheat",
                description="Coolant temperature exceeds safe threshold",
                subsystem=Subsystem.COOLING.value,
                severity=Severity.HIGH.value,
                priority=2,
                condition=RuleCondition(
                    signal="temp",
                    operator=">",
                    threshold=105.0,
                    duration_ms=3000,
                    debounce_count=3,
                ),
                recovery_condition=RuleCondition(
                    signal="temp",
                    operator="<",
                    threshold=100.0,
                ),
                cooldown_s=30.0,
                possible_causes=[
                    "Thermostat stuck closed",
                    "Low coolant level",
                    "Radiator fan failure",
                    "Water pump degradation",
                    "Radiator blockage",
                ],
                confidence=0.85,
                recommendation="Stop engine. Check coolant level. Inspect thermostat and fan.",
                estimated_repair_time="1-3 hours",
                related_dtcs=["P0217", "P0128"],
                health_score_impact=-15.0,
            ),
            FaultRule(
                rule_id="LOW_BATTERY_VOLTAGE",
                name="Low Battery Voltage",
                description="Battery voltage below minimum threshold",
                subsystem=Subsystem.BATTERY.value,
                severity=Severity.MEDIUM.value,
                priority=3,
                condition=RuleCondition(
                    signal="battery",
                    operator="<",
                    threshold=11.5,
                    duration_ms=5000,
                    debounce_count=5,
                ),
                recovery_condition=RuleCondition(
                    signal="battery",
                    operator=">",
                    threshold=12.0,
                ),
                cooldown_s=60.0,
                possible_causes=[
                    "Alternator failure",
                    "Battery end of life",
                    "Parasitic drain",
                    "Loose battery terminal",
                    "Belt slip",
                ],
                confidence=0.78,
                recommendation="Check alternator output. Test battery. Inspect terminals.",
                estimated_repair_time="0.5-2 hours",
                related_dtcs=["P0562"],
                health_score_impact=-10.0,
            ),
            FaultRule(
                rule_id="RPM_REDLINE",
                name="Engine Redline",
                description="Engine RPM exceeds redline threshold",
                subsystem=Subsystem.ENGINE.value,
                severity=Severity.MEDIUM.value,
                priority=3,
                condition=RuleCondition(
                    signal="rpm",
                    operator=">",
                    threshold=6500.0,
                    duration_ms=1000,
                    debounce_count=2,
                ),
                recovery_condition=RuleCondition(
                    signal="rpm",
                    operator="<",
                    threshold=6000.0,
                ),
                cooldown_s=10.0,
                possible_causes=[
                    "Aggressive driving",
                    "Transmission slip",
                    "Governor failure",
                ],
                confidence=0.9,
                recommendation="Reduce throttle. Check for transmission issues if persistent.",
                estimated_repair_time="N/A",
                health_score_impact=-5.0,
            ),
            FaultRule(
                rule_id="LOW_FUEL",
                name="Low Fuel Level",
                description="Fuel level below warning threshold",
                subsystem=Subsystem.FUEL.value,
                severity=Severity.LOW.value,
                priority=4,
                condition=RuleCondition(
                    signal="fuel",
                    operator="<",
                    threshold=15.0,
                    duration_ms=2000,
                    debounce_count=2,
                ),
                recovery_condition=RuleCondition(
                    signal="fuel",
                    operator=">",
                    threshold=20.0,
                ),
                cooldown_s=300.0,
                possible_causes=["Fuel level low"],
                confidence=0.99,
                recommendation="Refuel soon to avoid fuel pump damage.",
                estimated_repair_time="N/A",
                health_score_impact=-2.0,
            ),
            FaultRule(
                rule_id="CRITICAL_OVERHEAT",
                name="Critical Engine Overheat",
                description="Coolant temperature at critical level - engine damage imminent",
                subsystem=Subsystem.COOLING.value,
                severity=Severity.CRITICAL.value,
                priority=1,
                condition=RuleCondition(
                    signal="temp",
                    operator=">",
                    threshold=120.0,
                    duration_ms=1000,
                    debounce_count=2,
                ),
                recovery_condition=RuleCondition(
                    signal="temp",
                    operator="<",
                    threshold=110.0,
                ),
                cooldown_s=60.0,
                possible_causes=[
                    "Complete cooling system failure",
                    "Coolant leak",
                    "Head gasket failure",
                ],
                confidence=0.92,
                recommendation="STOP ENGINE IMMEDIATELY. Do not continue driving. Tow to service center.",
                estimated_repair_time="2-8 hours",
                related_dtcs=["P0217", "P0219"],
                health_score_impact=-35.0,
            ),
        ]

    def validate(self) -> List[str]:
        """Validate loaded rules. Returns list of issues."""
        issues = []
        for rule in self._rules:
            if not rule.rule_id:
                issues.append(f"Rule missing ID")
            if not rule.condition:
                issues.append(f"Rule '{rule.rule_id}' has no condition")
            if rule.condition and not rule.condition.signal:
                issues.append(f"Rule '{rule.rule_id}' condition has no signal")
        return issues