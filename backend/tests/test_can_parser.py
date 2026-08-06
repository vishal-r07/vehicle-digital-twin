"""
============================================================================
AutoTwin AI - CAN Parser Tests
============================================================================
Tests for CAN frame decoding, signal extraction, and serial frame parsing.

Test Categories:
  - Serial frame decoding (pre-parsed key-value)
  - Raw CAN frame decoding (bit extraction)
  - Signal validation and clamping
  - Intel/Motorola byte order
  - Signed/unsigned handling
  - Edge cases (empty, malformed, out-of-range)
============================================================================
"""

import pytest

from app.can.frame_parser import CANFrameParser, DecodedFrame
from app.can.signal_definitions import (
    Phase1Signals,
    get_signal_config,
    get_signals_for_can_id,
    get_all_signal_names,
)
from app.can.dbc_loader import DBCParser, DBCSignal
from app.can.frame_buffer import FrameBuffer, BufferedFrame


# ============================================================================
# SERIAL FRAME DECODING TESTS
# ============================================================================


class TestSerialFrameDecoding:
    """Tests for decoding pre-parsed serial frames from STM32."""

    def test_decode_basic_serial_frame(self, can_parser, serial_frame_data):
        """Test decoding a complete serial frame."""
        decoded = can_parser.decode_serial_frame(serial_frame_data)

        assert decoded.is_valid
        assert decoded.signal_count > 0
        assert decoded.signals["speed"] == 58.0
        assert decoded.signals["rpm"] == 2450
        assert decoded.signals["fuel"] == 82.0
        assert decoded.signals["temp"] == 91
        assert decoded.signals["battery"] == 12.5

    def test_decode_gear_as_string(self, can_parser, serial_frame_data):
        """Gear should remain as string, not converted to number."""
        decoded = can_parser.decode_serial_frame(serial_frame_data)
        assert decoded.signals["gear"] == "D"
        assert isinstance(decoded.signals["gear"], str)

    def test_decode_door_as_string(self, can_parser, serial_frame_data):
        """Door status should remain as string."""
        decoded = can_parser.decode_serial_frame(serial_frame_data)
        assert decoded.signals["door"] == "Closed"

    def test_decode_brake_as_integer(self, can_parser, serial_frame_data):
        """Brake should be integer 0 or 1."""
        decoded = can_parser.decode_serial_frame(serial_frame_data)
        assert decoded.signals["brake"] == 0
        assert isinstance(decoded.signals["brake"], int)

    def test_decode_negative_steering(self, can_parser, serial_frame_data):
        """Negative steering angle should be preserved."""
        decoded = can_parser.decode_serial_frame(serial_frame_data)
        assert decoded.signals["steering"] == -12.0

    def test_decode_empty_frame(self, can_parser):
        """Empty frame should produce empty result."""
        decoded = can_parser.decode_serial_frame({})
        assert decoded.signal_count == 0
        assert decoded.is_valid

    def test_decode_partial_frame(self, can_parser):
        """Partial frame (missing signals) should still work."""
        partial = {"Speed": "45.0", "RPM": "1800"}
        decoded = can_parser.decode_serial_frame(partial)

        assert decoded.signals["speed"] == 45.0
        assert decoded.signals["rpm"] == 1800
        assert decoded.signal_count == 2

    def test_decode_invalid_value_gracefully(self, can_parser):
        """Invalid values should not crash parser."""
        data = {"Speed": "not_a_number", "RPM": "2000"}
        decoded = can_parser.decode_serial_frame(data)

        # RPM should parse, speed should be skipped or error logged
        assert decoded.signals.get("rpm") == 2000

    def test_decode_metadata_fields_skipped(self, can_parser, serial_frame_data):
        """Metadata fields (FrameCount, Uptime, Seq) should be skipped."""
        decoded = can_parser.decode_serial_frame(serial_frame_data)

        assert "FrameCount" not in decoded.signals
        assert "Uptime" not in decoded.signals
        assert "Seq" not in decoded.signals

    def test_decode_wheel_speeds(self, can_parser, serial_frame_data):
        """Individual wheel speeds should be decoded."""
        decoded = can_parser.decode_serial_frame(serial_frame_data)

        assert abs(decoded.signals["wheel_fl"] - 57.8) < 0.01
        assert abs(decoded.signals["wheel_fr"] - 58.1) < 0.01

    def test_to_state_update_conversion(self, can_parser, serial_frame_data):
        """Test conversion to state update dictionary."""
        decoded = can_parser.decode_serial_frame(serial_frame_data)
        state_update = can_parser.to_state_update(decoded)

        assert "speed" in state_update
        assert "rpm" in state_update
        assert state_update["speed"] == 58.0


# ============================================================================
# RAW CAN FRAME DECODING TESTS
# ============================================================================


class TestRawCANFrameDecoding:
    """Tests for decoding raw CAN frames (bit-level extraction)."""

    def test_decode_speed_frame(self, can_parser, raw_can_speed_frame):
        """Test decoding speed from raw CAN bytes (0x100)."""
        decoded = can_parser.decode_can_frame(0x100, raw_can_speed_frame)

        assert decoded.is_valid
        assert abs(decoded.signals["speed"] - 58.0) < 0.01

    def test_decode_rpm_frame(self, can_parser, raw_can_rpm_frame):
        """Test decoding RPM from raw CAN bytes (0x101)."""
        decoded = can_parser.decode_can_frame(0x101, raw_can_rpm_frame)

        assert decoded.is_valid
        assert decoded.signals["rpm"] == 2450

    def test_decode_temp_frame(self, can_parser, raw_can_temp_frame):
        """Test decoding temperature with offset (0x103)."""
        decoded = can_parser.decode_can_frame(0x103, raw_can_temp_frame)

        assert decoded.is_valid
        assert decoded.signals["temp"] == 91  # 131 - 40 = 91

    def test_decode_unknown_can_id(self, can_parser):
        """Unknown CAN ID should produce invalid result."""
        data = bytes([0x00] * 8)
        decoded = can_parser.decode_can_frame(0x999, data)

        assert not decoded.is_valid
        assert len(decoded.validation_errors) > 0

    def test_decode_zero_values(self, can_parser):
        """All-zero frame should decode to zero/minimum values."""
        data = bytes([0x00] * 8)
        decoded = can_parser.decode_can_frame(0x100, data)

        assert decoded.signals["speed"] == 0.0

    def test_decode_max_values(self, can_parser):
        """Maximum raw values should clamp to signal max."""
        # Speed max: 300 km/h → raw = 30000 = 0x7530
        data = bytes([0x30, 0x75, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        decoded = can_parser.decode_can_frame(0x100, data)

        assert decoded.signals["speed"] <= 300.0

    def test_decode_steering_signed(self, can_parser):
        """Test signed steering angle decoding (0x105)."""
        # Steering = -120.0° → raw = -1200 = 0xFB50 (signed 16-bit LE)
        raw = (-1200) & 0xFFFF  # Two's complement
        data = bytes([raw & 0xFF, (raw >> 8) & 0xFF, 0, 0, 0, 0, 0, 0])
        decoded = can_parser.decode_can_frame(0x105, data)

        assert decoded.is_valid
        assert abs(decoded.signals["steering"] - (-120.0)) < 0.1


# ============================================================================
# SIGNAL DEFINITIONS TESTS
# ============================================================================


class TestSignalDefinitions:
    """Tests for Phase 1 signal configurations."""

    def test_all_phase1_signals_defined(self):
        """All 16 Phase 1 signals should be defined."""
        signals = Phase1Signals.get_all()
        assert len(signals) >= 16

    def test_signal_config_lookup(self):
        """Signal lookup by name should work."""
        config = get_signal_config("speed")
        assert config is not None
        assert config.can_id == 0x100
        assert config.factor == 0.01
        assert config.max_value == 300.0

    def test_signal_config_not_found(self):
        """Non-existent signal should return None."""
        config = get_signal_config("nonexistent_signal")
        assert config is None

    def test_signals_for_can_id(self):
        """CAN ID lookup should return associated signals."""
        signals = get_signals_for_can_id(0x100)
        assert len(signals) >= 1
        assert signals[0].name == "speed"

    def test_signal_conversion_roundtrip(self):
        """raw → physical → raw should be lossless for integer signals."""
        config = get_signal_config("rpm")
        raw = 2450
        physical = config.raw_to_physical(raw)
        raw_back = config.physical_to_raw(physical)
        assert raw_back == raw

    def test_signal_validation(self):
        """Signal validation should catch out-of-range values."""
        config = get_signal_config("speed")
        assert config.validate(58.0) is True
        assert config.validate(500.0) is False
        assert config.validate(-10.0) is False

    def test_signal_clamping(self):
        """Signal clamping should limit to valid range."""
        config = get_signal_config("speed")
        assert config.clamp(500.0) == 300.0
        assert config.clamp(-10.0) == 0.0
        assert config.clamp(58.0) == 58.0

    def test_get_all_signal_names(self):
        """Should return list of all signal names."""
        names = get_all_signal_names()
        assert "speed" in names
        assert "rpm" in names
        assert "temp" in names
        assert len(names) >= 16


# ============================================================================
# DBC PARSER TESTS
# ============================================================================


class TestDBCParser:
    """Tests for DBC file parsing."""

    SAMPLE_DBC = '''
VERSION "1.0"

BO_ 256 VehicleSpeed: 8 ECU_CHASSIS
 SG_ Speed : 0|16@1+ (0.01,0) [0|300] "km/h" Vector__XXX

BO_ 257 EngineRPM: 8 ECU_ENGINE
 SG_ RPM : 0|16@1+ (1,0) [0|8000] "rpm" Vector__XXX

BO_ 259 CoolantTemp: 8 ECU_ENGINE
 SG_ Temperature : 0|8@1+ (1,-40) [-40|215] "degC" Vector__XXX

BO_ 264 GearPosition: 8 ECU_CHASSIS
 SG_ Gear : 0|8@1+ (1,0) [0|6] "" Vector__XXX

VAL_ 264 Gear 0 "P" 1 "R" 2 "N" 3 "D" 4 "S" 5 "L" 6 "M" ;
'''

    def test_parse_dbc_from_string(self):
        """Test parsing DBC content from string."""
        parser = DBCParser("test.dbc")
        dbc = parser.load_from_string(self.SAMPLE_DBC)

        assert dbc.message_count == 4
        assert dbc.signal_count == 4

    def test_get_message_by_id(self):
        """Test message lookup by CAN ID."""
        parser = DBCParser("test.dbc")
        parser.load_from_string(self.SAMPLE_DBC)

        msg = parser.get_message(256)
        assert msg is not None
        assert msg.name == "VehicleSpeed"
        assert msg.dlc == 8

    def test_get_signal_by_name(self):
        """Test signal lookup within message."""
        parser = DBCParser("test.dbc")
        parser.load_from_string(self.SAMPLE_DBC)

        sig = parser.get_signal(256, "Speed")
        assert sig is not None
        assert sig.factor == 0.01
        assert sig.unit == "km/h"
        assert sig.bit_length == 16

    def test_signal_decode(self):
        """Test signal raw-to-physical conversion."""
        parser = DBCParser("test.dbc")
        parser.load_from_string(self.SAMPLE_DBC)

        sig = parser.get_signal(256, "Speed")
        physical = sig.decode_raw(5800)
        assert abs(physical - 58.0) < 0.01

    def test_temperature_offset(self):
        """Test signal with offset (temperature)."""
        parser = DBCParser("test.dbc")
        parser.load_from_string(self.SAMPLE_DBC)

        sig = parser.get_signal(259, "Temperature")
        assert sig.offset == -40.0

        physical = sig.decode_raw(131)  # 131 - 40 = 91
        assert physical == 91.0

    def test_value_descriptions(self):
        """Test VAL_ value descriptions parsing."""
        parser = DBCParser("test.dbc")
        parser.load_from_string(self.SAMPLE_DBC)

        sig = parser.get_signal(264, "Gear")
        assert sig is not None
        assert sig.value_descriptions.get(0) == "P"
        assert sig.value_descriptions.get(3) == "D"

    def test_validation(self):
        """Test DBC validation."""
        parser = DBCParser("test.dbc")
        parser.load_from_string(self.SAMPLE_DBC)

        issues = parser.validate()
        assert len(issues) == 0  # Should be valid

    def test_empty_dbc(self):
        """Empty DBC should parse without error."""
        parser = DBCParser("test.dbc")
        dbc = parser.load_from_string("")

        assert dbc.message_count == 0
        assert dbc.signal_count == 0


# ============================================================================
# FRAME BUFFER TESTS
# ============================================================================


class TestFrameBuffer:
    """Tests for the CAN frame ring buffer."""

    def test_push_and_pop(self):
        """Basic push/pop operations."""
        buffer = FrameBuffer(capacity=10)

        buffer.push_parsed({"speed": 50.0})
        assert buffer.size == 1

        frame = buffer.pop()
        assert frame is not None
        assert frame.signals["speed"] == 50.0
        assert buffer.size == 0

    def test_fifo_order(self):
        """Frames should come out in FIFO order."""
        buffer = FrameBuffer(capacity=10)

        for i in range(5):
            buffer.push_parsed({"speed": float(i)})

        for i in range(5):
            frame = buffer.pop()
            assert frame.signals["speed"] == float(i)

    def test_capacity_limit(self):
        """Buffer should not exceed capacity."""
        buffer = FrameBuffer(capacity=5)

        for i in range(10):
            buffer.push_parsed({"speed": float(i)})

        assert buffer.size == 5  # Capped at capacity

    def test_overflow_tracking(self):
        """Overflow should be tracked in stats."""
        buffer = FrameBuffer(capacity=3)

        for i in range(10):
            buffer.push_parsed({"speed": float(i)})

        stats = buffer.get_stats()
        assert stats["total_dropped"] > 0

    def test_pop_empty_returns_none(self):
        """Pop from empty buffer should return None."""
        buffer = FrameBuffer(capacity=10)
        assert buffer.pop() is None

    def test_pop_batch(self):
        """Batch pop should return multiple frames."""
        buffer = FrameBuffer(capacity=20)

        for i in range(10):
            buffer.push_parsed({"speed": float(i)})

        batch = buffer.pop_batch(5)
        assert len(batch) == 5
        assert buffer.size == 5

    def test_time_window_query(self):
        """Time-windowed retrieval should filter correctly."""
        import time
        buffer = FrameBuffer(capacity=100)

        # Push frames with current timestamps
        for i in range(10):
            buffer.push_parsed({"speed": float(i)})

        recent = buffer.get_last_n_seconds(5.0)
        assert len(recent) == 10  # All recent

    def test_export_and_import(self):
        """Export/import round-trip should preserve data."""
        buffer = FrameBuffer(capacity=10)

        for i in range(5):
            buffer.push_parsed({"speed": float(i * 10), "rpm": 1000 + i})

        exported = buffer.export_to_list()
        assert len(exported) == 5

        # Import into new buffer
        buffer2 = FrameBuffer(capacity=10)
        count = buffer2.import_from_list(exported)
        assert count == 5
        assert buffer2.size == 5

    def test_sequence_numbering(self):
        """Frames should get incrementing sequence numbers."""
        buffer = FrameBuffer(capacity=10)

        buffer.push_parsed({"speed": 10.0})
        buffer.push_parsed({"speed": 20.0})
        buffer.push_parsed({"speed": 30.0})

        frame1 = buffer.pop()
        frame2 = buffer.pop()
        frame3 = buffer.pop()

        assert frame1.sequence == 1
        assert frame2.sequence == 2
        assert frame3.sequence == 3