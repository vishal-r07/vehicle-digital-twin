"""
============================================================================
AutoTwin AI - WebSocket Tests
============================================================================
Tests for WebSocket connection management and message broadcasting.

Test Categories:
  - Connection management
  - Message broadcasting
  - Subscription filtering
  - Message format validation
  - Disconnect handling
============================================================================
"""

import asyncio
import json

import pytest
import pytest_asyncio

from app.api.endpoints.ws import WebSocketManager
from app.api.schemas.ws_messages import (
    WSMessageEnvelope,
    WSVehicleStatePayload,
    create_ws_message,
    SERVER_MESSAGE_TYPES,
    CLIENT_MESSAGE_TYPES,
)


# ============================================================================
# WEBSOCKET MANAGER TESTS
# ============================================================================


class TestWebSocketManager:
    """Tests for WebSocketManager."""

    def test_initial_state(self):
        """New manager should have no connections."""
        manager = WebSocketManager()
        assert manager.client_count == 0

    def test_stats_initial(self):
        """Initial stats should be zero."""
        manager = WebSocketManager()
        stats = manager.get_stats()
        assert stats["active_connections"] == 0
        assert stats["messages_sent"] == 0

    @pytest.mark.asyncio
    async def test_broadcast_no_clients(self):
        """Broadcast with no clients should not error."""
        manager = WebSocketManager()
        # Should not raise
        await manager.broadcast({"type": "test", "payload": {}})
        assert manager.get_stats()["messages_sent"] == 0

    @pytest.mark.asyncio
    async def test_close_all_empty(self):
        """close_all with no connections should not error."""
        manager = WebSocketManager()
        await manager.close_all()
        assert manager.client_count == 0


# ============================================================================
# MESSAGE FORMAT TESTS
# ============================================================================


class TestWSMessageFormats:
    """Tests for WebSocket message schemas."""

    def test_vehicle_state_payload(self):
        """Vehicle state payload should serialize correctly."""
        payload = WSVehicleStatePayload(
            speed=58.0,
            rpm=2450,
            fuel=82.0,
            temp=91.0,
            battery=12.5,
            gear="D",
        )

        d = payload.model_dump()
        assert d["speed"] == 58.0
        assert d["rpm"] == 2450
        assert d["gear"] == "D"

    def test_create_ws_message(self):
        """create_ws_message helper should produce valid envelope."""
        msg = create_ws_message("vehicle_state", {"speed": 58.0}, seq=100)

        assert msg["type"] == "vehicle_state"
        assert msg["seq"] == 100
        assert msg["payload"]["speed"] == 58.0
        assert "timestamp" in msg

    def test_message_envelope_validation(self):
        """WSMessageEnvelope should validate required fields."""
        envelope = WSMessageEnvelope(
            type="heartbeat",
            seq=1,
            timestamp=1705312200.0,
            payload={"uptime_s": 3600},
        )
        assert envelope.type == "heartbeat"

    def test_server_message_types_registry(self):
        """Server message type registry should be complete."""
        expected_types = [
            "vehicle_state", "fault_event", "fault_resolved",
            "health_update", "timeline_event", "scenario_update",
            "connection_ack", "heartbeat", "error",
        ]
        for msg_type in expected_types:
            assert msg_type in SERVER_MESSAGE_TYPES, f"Missing: {msg_type}"

    def test_client_message_types_registry(self):
        """Client message type registry should be complete."""
        expected_types = [
            "subscribe", "request_state",
            "scenario_command", "acknowledge_fault",
        ]
        for msg_type in expected_types:
            assert msg_type in CLIENT_MESSAGE_TYPES, f"Missing: {msg_type}"

    def test_message_json_roundtrip(self):
        """Messages should survive JSON serialization."""
        msg = create_ws_message("fault_event", {
            "fault_id": "F-TEST",
            "severity": "HIGH",
            "message": "Test fault",
        })

        # Serialize
        json_str = json.dumps(msg)

        # Deserialize
        parsed = json.loads(json_str)
        assert parsed["type"] == "fault_event"
        assert parsed["payload"]["fault_id"] == "F-TEST"


# ============================================================================
# MESSAGE CONTENT TESTS
# ============================================================================


class TestWSMessageContent:
    """Tests for specific message content requirements."""

    def test_vehicle_state_has_all_signals(self):
        """Vehicle state message should include all primary signals."""
        payload = WSVehicleStatePayload()
        d = payload.model_dump()

        required_fields = [
            "speed", "rpm", "fuel", "temp", "battery",
            "steering", "brake", "accelerator", "gear",
            "door", "indicator", "headlight",
        ]

        for field in required_fields:
            assert field in d, f"Missing field: {field}"

    def test_connection_ack_structure(self):
        """Connection ACK should have required fields."""
        from app.api.schemas.ws_messages import WSConnectionAckPayload

        ack = WSConnectionAckPayload(
            client_id="test-123",
            server_version="1.0.0",
            update_rate_hz=20,
        )

        d = ack.model_dump()
        assert d["client_id"] == "test-123"
        assert d["update_rate_hz"] == 20
        assert "features" in d

    def test_fault_event_payload_structure(self):
        """Fault event should have diagnostic fields."""
        from app.api.schemas.ws_messages import WSFaultEventPayload

        payload = WSFaultEventPayload(
            fault_id="F-001",
            rule_id="COOLANT_OVERHEAT",
            severity="HIGH",
            confidence=0.85,
            priority=2,
            subsystem="cooling",
            message="Engine overheating",
            possible_causes=["Thermostat failure", "Low coolant"],
        )

        d = payload.model_dump()
        assert d["severity"] == "HIGH"
        assert len(d["possible_causes"]) == 2

    def test_heartbeat_payload(self):
        """Heartbeat should include system metrics."""
        from app.api.schemas.ws_messages import WSHeartbeatPayload

        payload = WSHeartbeatPayload(
            uptime_s=3600,
            active_connections=3,
            frames_processed=72000,
        )

        d = payload.model_dump()
        assert d["uptime_s"] == 3600
        assert d["active_connections"] == 3