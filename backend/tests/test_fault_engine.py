"""
============================================================================
AutoTwin AI - Fault Engine Tests
============================================================================
Tests for fault detection, rule evaluation, and fault lifecycle.

Test Categories:
  - Rule evaluation (threshold, debounce, duration)
  - Fault triggering and resolution
  - Cooldown behavior
  - Severity classification
  - Active fault queries
  - Rule enable/disable
============================================================================
"""

import asyncio
import time

import pytest
import pytest_asyncio

from app.core.event_bus import EventBus
from app.core.constants import Severity
from app.diagnostics.fault_engine import FaultEngine, FaultEvent
from app.diagnostics.fault_rules import FaultRule, RuleCondition, RuleLoader


# ============================================================================
# RULE CONDITION TESTS
# ============================================================================


class TestRuleCondition:
    """Tests for individual rule condition evaluation."""

    def test_greater_than(self):
        """'>' operator should work."""
        cond = RuleCondition(signal="temp", operator=">", threshold=105.0)
        assert cond.evaluate(110.0) is True
        assert cond.evaluate(100.0) is False
        assert cond.evaluate(105.0) is False  # Not strictly greater

    def test_less_than(self):
        """'<' operator should work."""
        cond = RuleCondition(signal="battery", operator="<", threshold=11.5)
        assert cond.evaluate(11.0) is True
        assert cond.evaluate(12.0) is False

    def test_greater_equal(self):
        """'>=' operator should work."""
        cond = RuleCondition(signal="rpm", operator=">=", threshold=6500.0)
        assert cond.evaluate(6500.0) is True
        assert cond.evaluate(6499.0) is False

    def test_between(self):
        """'between' operator should work."""
        cond = RuleCondition(
            signal="temp", operator="between",
            threshold=90.0, threshold_high=100.0
        )
        assert cond.evaluate(95.0) is True
        assert cond.evaluate(85.0) is False
        assert cond.evaluate(105.0) is False

    def test_change_operator(self):
        """'change' operator should detect delta."""
        cond = RuleCondition(signal="speed", operator="change", threshold=10.0)
        assert cond.evaluate(60.0, prev_value=45.0) is True   # Delta = 15
        assert cond.evaluate(60.0, prev_value=55.0) is False  # Delta = 5

    def test_equal(self):
        """'==' operator should work."""
        cond = RuleCondition(signal="gear", operator="==", threshold=0.0)
        assert cond.evaluate(0.0) is True
        assert cond.evaluate(1.0) is False


# ============================================================================
# FAULT RULE TESTS
# ============================================================================


class TestFaultRule:
    """Tests for FaultRule evaluation logic."""

    def test_rule_triggers_on_condition(self):
        """Rule should trigger when condition is met."""
        rule = FaultRule(
            rule_id="TEST_RULE",
            name="Test Rule",
            condition=RuleCondition(signal="temp", operator=">", threshold=105.0),
        )

        triggered = rule.evaluate(signal_value=110.0)
        assert triggered is True

    def test_rule_does_not_trigger_below_threshold(self):
        """Rule should not trigger below threshold."""
        rule = FaultRule(
            rule_id="TEST_RULE",
            name="Test Rule",
            condition=RuleCondition(signal="temp", operator=">", threshold=105.0),
        )

        triggered = rule.evaluate(signal_value=100.0)
        assert triggered is False

    def test_debounce_requirement(self):
        """Rule with debounce_count should require consecutive triggers."""
        rule = FaultRule(
            rule_id="TEST_RULE",
            name="Test Rule",
            condition=RuleCondition(
                signal="temp", operator=">", threshold=105.0,
                debounce_count=3,
            ),
        )

        # First two evaluations should not trigger
        assert rule.evaluate(signal_value=110.0) is False
        assert rule.evaluate(signal_value=110.0) is False
        # Third should trigger
        assert rule.evaluate(signal_value=110.0) is True

    def test_debounce_resets_on_normal(self):
        """Debounce counter should reset when condition clears."""
        rule = FaultRule(
            rule_id="TEST_RULE",
            name="Test Rule",
            condition=RuleCondition(
                signal="temp", operator=">", threshold=105.0,
                debounce_count=3,
            ),
        )

        rule.evaluate(signal_value=110.0)  # Count = 1
        rule.evaluate(signal_value=110.0)  # Count = 2
        rule.evaluate(signal_value=90.0)   # Reset
        rule.evaluate(signal_value=110.0)  # Count = 1 (not 3)

        assert rule.evaluate(signal_value=110.0) is False  # Count = 2

    def test_disabled_rule_does_not_trigger(self):
        """Disabled rule should never trigger."""
        rule = FaultRule(
            rule_id="TEST_RULE",
            name="Test Rule",
            enabled=False,
            condition=RuleCondition(signal="temp", operator=">", threshold=105.0),
        )

        assert rule.evaluate(signal_value=110.0) is False

    def test_rule_reset(self):
        """Reset should clear internal state."""
        rule = FaultRule(
            rule_id="TEST_RULE",
            name="Test Rule",
            condition=RuleCondition(
                signal="temp", operator=">", threshold=105.0,
                debounce_count=2,
            ),
        )

        rule.evaluate(signal_value=110.0)
        rule.reset()

        # After reset, debounce starts fresh
        assert rule.evaluate(signal_value=110.0) is False

    def test_rule_from_dict(self):
        """FaultRule.from_dict should parse correctly."""
        data = {
            "id": "TEST_RULE",
            "name": "Test Rule",
            "subsystem": "cooling",
            "severity": "HIGH",
            "condition": {
                "signal": "temp",
                "operator": ">",
                "threshold": 105,
                "duration_ms": 3000,
            },
            "diagnosis": {
                "possible_causes": ["Thermostat failure"],
                "confidence": 0.85,
            },
        }

        rule = FaultRule.from_dict(data)
        assert rule.rule_id == "TEST_RULE"
        assert rule.severity == "HIGH"
        assert rule.condition.signal == "temp"
        assert rule.condition.threshold == 105.0
        assert len(rule.possible_causes) == 1


# ============================================================================
# RULE LOADER TESTS
# ============================================================================


class TestRuleLoader:
    """Tests for rule loading from YAML and defaults."""

    def test_load_default_rules(self):
        """Default rules should load without file."""
        loader = RuleLoader()
        rules = loader.load()

        assert len(rules) >= 5
        rule_ids = [r.rule_id for r in rules]
        assert "COOLANT_OVERHEAT" in rule_ids
        assert "LOW_BATTERY_VOLTAGE" in rule_ids

    def test_default_rules_have_conditions(self):
        """All default rules should have conditions."""
        loader = RuleLoader()
        rules = loader.load()

        for rule in rules:
            assert rule.condition is not None, f"Rule {rule.rule_id} missing condition"
            assert rule.condition.signal != "", f"Rule {rule.rule_id} missing signal"

    def test_load_from_dict(self):
        """Rules should load from dictionary."""
        data = {
            "rules": [
                {
                    "id": "CUSTOM_RULE",
                    "name": "Custom Rule",
                    "condition": {"signal": "speed", "operator": ">", "threshold": 200},
                }
            ]
        }

        loader = RuleLoader()
        rules = loader.load_from_dict(data)
        assert len(rules) == 1
        assert rules[0].rule_id == "CUSTOM_RULE"

    def test_validation(self):
        """Validation should catch issues."""
        loader = RuleLoader()
        loader.load()
        issues = loader.validate()
        assert len(issues) == 0  # Default rules should be valid


# ============================================================================
# FAULT ENGINE TESTS
# ============================================================================


class TestFaultEngine:
    """Tests for the FaultEngine (rule evaluation orchestrator)."""

    @pytest.mark.asyncio
    async def test_evaluate_triggers_fault(self, fault_engine):
        """Engine should detect faults from state."""
        faults = fault_engine.evaluate_state({"temp": 112.0, "rpm": 3000})

        assert len(faults) > 0
        assert any(f.rule_id == "COOLANT_OVERHEAT" for f in faults)

    @pytest.mark.asyncio
    async def test_evaluate_no_fault_normal_state(self, fault_engine):
        """Normal state should not trigger faults."""
        faults = fault_engine.evaluate_state({
            "temp": 90.0,
            "rpm": 2000,
            "battery": 12.6,
            "fuel": 80.0,
        })

        assert len(faults) == 0

    @pytest.mark.asyncio
    async def test_active_faults_tracking(self, fault_engine):
        """Active faults should be tracked."""
        fault_engine.evaluate_state({"temp": 112.0})

        active = fault_engine.get_active_faults()
        assert len(active) > 0

    @pytest.mark.asyncio
    async def test_fault_resolution(self, fault_engine):
        """Faults should be resolvable."""
        fault_engine.evaluate_state({"temp": 112.0})
        active = fault_engine.get_active_faults()
        assert len(active) > 0

        # Resolve
        rule_id = active[0].rule_id
        resolved = await fault_engine.resolve_fault(rule_id)
        assert resolved is not None
        assert resolved.resolved is True

        # Should no longer be active
        active_after = fault_engine.get_active_faults()
        assert len(active_after) < len(active)

    @pytest.mark.asyncio
    async def test_fault_acknowledgment(self, fault_engine):
        """Faults should be acknowledgeable."""
        fault_engine.evaluate_state({"temp": 112.0})
        active = fault_engine.get_active_faults()

        fault_id = active[0].fault_id
        success = fault_engine.acknowledge_fault(fault_id)
        assert success is True

    @pytest.mark.asyncio
    async def test_fault_history(self, fault_engine):
        """Fault history should accumulate."""
        fault_engine.evaluate_state({"temp": 112.0})
        await fault_engine.resolve_fault("COOLANT_OVERHEAT")

        history = fault_engine.get_fault_history()
        assert len(history) >= 1

    @pytest.mark.asyncio
    async def test_fault_severity(self, fault_engine):
        """Faults should have correct severity."""
        faults = fault_engine.evaluate_state({"temp": 125.0})

        # Critical overheat should be CRITICAL severity
        critical = [f for f in faults if f.severity == Severity.CRITICAL.value]
        assert len(critical) > 0

    @pytest.mark.asyncio
    async def test_multiple_faults(self, fault_engine):
        """Multiple simultaneous faults should be detected."""
        faults = fault_engine.evaluate_state({
            "temp": 112.0,
            "battery": 10.0,
            "rpm": 7000,
        })

        assert len(faults) >= 2  # At least overheat + battery

    @pytest.mark.asyncio
    async def test_rule_enable_disable(self, fault_engine):
        """Rules should be toggleable."""
        fault_engine.disable_rule("COOLANT_OVERHEAT")

        faults = fault_engine.evaluate_state({"temp": 112.0})
        overheat_faults = [f for f in faults if f.rule_id == "COOLANT_OVERHEAT"]
        assert len(overheat_faults) == 0

        fault_engine.enable_rule("COOLANT_OVERHEAT")

    @pytest.mark.asyncio
    async def test_fault_event_structure(self, fault_engine):
        """FaultEvent should have all required fields."""
        faults = fault_engine.evaluate_state({"temp": 112.0})
        assert len(faults) > 0

        fault = faults[0]
        assert fault.fault_id != ""
        assert fault.rule_id != ""
        assert fault.severity in [s.value for s in Severity]
        assert fault.message != ""
        assert fault.timestamp > 0
        assert fault.is_active is True

    @pytest.mark.asyncio
    async def test_get_stats(self, fault_engine):
        """Stats should return valid data."""
        fault_engine.evaluate_state({"temp": 112.0})
        stats = fault_engine.get_stats()

        assert stats["active_faults"] >= 1
        assert stats["total_evaluations"] > 0
        assert stats["rules_loaded"] > 0