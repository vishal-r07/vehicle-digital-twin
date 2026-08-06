"""
============================================================================
AutoTwin AI - CAN Frame Parser
============================================================================
Decodes raw CAN frames into physical signal values.

Supports two input modes:
  1. Raw CAN frames (from USB-CAN adapter): bit-level extraction
  2. Pre-parsed serial frames (from STM32): key-value mapping

The parser applies:
  - Bit extraction (Intel/Motorola byte order)
  - Signed/unsigned interpretation
  - Factor/offset conversion to physical units
  - Range validation and clamping
  - Signal-to-state routing

Usage:
    parser = CANFrameParser(event_bus)
    parser.load_signal_configs()

    # Decode raw CAN frame
    signals = parser.decode_can_frame(can_id=0x100, data=b'\\x10\\x27\\x00...')

    # Decode pre-parsed serial frame
    state_update = parser.decode_serial_frame({"Speed": "58.00", "RPM": "2450"})
============================================================================
"""

import struct
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.core.constants import EventType, CANId
from app.core.event_bus import EventBus
from app.core.exceptions import InvalidSignalError
from app.can.signal_definitions import (
    Phase1Signals,
    SignalConfig,
    get_signal_config,
    get_signals_for_can_id,
    get_gear_mapping,
    get_door_bit_labels,
)


# ============================================================================
# DECODED FRAME DATA STRUCTURE
# ============================================================================


@dataclass
class DecodedFrame:
    """
    Result of decoding a CAN frame.

    Contains all extracted signals with their physical values,
    validation status, and metadata.
    """

    can_id: int = 0
    timestamp: float = field(default_factory=time.time)
    signals: Dict[str, float] = field(default_factory=dict)
    raw_values: Dict[str, int] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    is_valid: bool = True
    decode_time_us: float = 0.0  # Decode duration in microseconds

    @property
    def signal_count(self) -> int:
        return len(self.signals)

    def get(self, name: str, default: float = 0.0) -> float:
        """Get a decoded signal value."""
        return self.signals.get(name, default)


# ============================================================================
# CAN FRAME PARSER
# ============================================================================


class CANFrameParser:
    """
    Decodes CAN frames into physical signal values.

    Handles both:
      - Raw CAN bytes (bit-level extraction from USB-CAN)
      - Pre-parsed serial data (key-value from STM32)

    Thread-safe: No mutable state during decode operations.
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize the frame parser.

        Args:
            event_bus: Optional event bus for emitting decode events.
        """
        self._event_bus = event_bus
        self._signal_configs: Dict[str, SignalConfig] = Phase1Signals.get_all()
        self._can_id_map: Dict[int, List[SignalConfig]] = {}

        # Build CAN ID → signals mapping
        for config in self._signal_configs.values():
            if config.can_id not in self._can_id_map:
                self._can_id_map[config.can_id] = []
            self._can_id_map[config.can_id].append(config)

        # Statistics
        self._frames_decoded: int = 0
        self._decode_errors: int = 0
        self._validation_warnings: int = 0

        logger.info(
            f"CANFrameParser: initialized with {len(self._signal_configs)} signal definitions"
        )

    # ========================================================================
    # RAW CAN FRAME DECODING (Bit-level)
    # ========================================================================

    def decode_can_frame(self, can_id: int, data: bytes, dlc: int = 8) -> DecodedFrame:
        """
        Decode a raw CAN frame using bit-level extraction.

        Args:
            can_id: CAN arbitration ID
            data: Payload bytes (up to 8)
            dlc: Data length code

        Returns:
            DecodedFrame with extracted physical values.
        """
        start_time = time.perf_counter()
        result = DecodedFrame(can_id=can_id)

        # Get signal configs for this CAN ID
        configs = self._can_id_map.get(can_id, [])
        if not configs:
            result.is_valid = False
            result.validation_errors.append(f"No signal definitions for CAN ID 0x{can_id:03X}")
            return result

        # Decode each signal
        for config in configs:
            try:
                raw_value = self._extract_signal(data, config)
                physical_value = config.raw_to_physical(raw_value)

                # Validate
                if not config.validate(physical_value):
                    physical_value = config.clamp(physical_value)
                    self._validation_warnings += 1

                result.signals[config.name] = physical_value
                result.raw_values[config.name] = raw_value

            except Exception as e:
                result.validation_errors.append(f"{config.name}: {e}")
                result.is_valid = False
                self._decode_errors += 1

        result.decode_time_us = (time.perf_counter() - start_time) * 1_000_000
        self._frames_decoded += 1

        return result

    def _extract_signal(self, data: bytes, config: SignalConfig) -> int:
        """
        Extract raw integer value from CAN data bytes.

        Handles both Intel (little-endian) and Motorola (big-endian)
        byte ordering, signed and unsigned values.
        """
        if len(data) < (config.start_bit + config.bit_length + 7) // 8:
            raise ValueError(f"Insufficient data for signal '{config.name}'")

        if config.byte_order == "little_endian":
            return self._extract_intel(data, config.start_bit, config.bit_length, config.is_signed)
        else:
            return self._extract_motorola(data, config.start_bit, config.bit_length, config.is_signed)

    def _extract_intel(
        self, data: bytes, start_bit: int, bit_length: int, is_signed: bool
    ) -> int:
        """
        Extract value using Intel (little-endian) byte order.

        Bits are numbered from LSB of byte 0.
        """
        result = 0
        bits_extracted = 0

        while bits_extracted < bit_length:
            byte_index = (start_bit + bits_extracted) // 8
            bit_in_byte = (start_bit + bits_extracted) % 8

            # How many bits can we read from this byte?
            bits_available = 8 - bit_in_byte
            bits_to_read = min(bits_available, bit_length - bits_extracted)

            # Extract bits from this byte
            mask = ((1 << bits_to_read) - 1) << bit_in_byte
            extracted = (data[byte_index] & mask) >> bit_in_byte

            # Place in result
            result |= extracted << bits_extracted
            bits_extracted += bits_to_read

        # Handle signed values (two's complement)
        if is_signed and bit_length > 0:
            if result & (1 << (bit_length - 1)):
                result -= 1 << bit_length

        return result

    def _extract_motorola(
        self, data: bytes, start_bit: int, bit_length: int, is_signed: bool
    ) -> int:
        """
        Extract value using Motorola (big-endian) byte order.

        Motorola bit numbering: MSB of first byte is start_bit.
        """
        result = 0
        current_bit = start_bit

        for i in range(bit_length):
            byte_index = current_bit // 8
            bit_in_byte = 7 - (current_bit % 8)  # Motorola numbering

            if byte_index < len(data):
                bit_value = (data[byte_index] >> bit_in_byte) & 1
                result = (result << 1) | bit_value

            # Move to next bit (Motorola order)
            if current_bit % 8 == 0:
                current_bit += 15  # Jump to next byte, MSB
            else:
                current_bit -= 1

        # Handle signed values
        if is_signed and bit_length > 0:
            if result & (1 << (bit_length - 1)):
                result -= 1 << bit_length

        return result

    # ========================================================================
    # SERIAL FRAME DECODING (Pre-parsed key-value)
    # ========================================================================

    def decode_serial_frame(self, signals: Dict[str, str]) -> DecodedFrame:
        """
        Decode a pre-parsed serial frame from STM32.

        The STM32 firmware already converts CAN data to physical values.
        This method parses the string values into proper types.

        Args:
            signals: Dictionary of {signal_name: string_value}
                     e.g., {"Speed": "58.00", "RPM": "2450", ...}

        Returns:
            DecodedFrame with typed physical values.
        """
        start_time = time.perf_counter()
        result = DecodedFrame(can_id=0)  # No specific CAN ID for serial frames

        # Mapping from serial protocol keys to internal signal names
        key_mapping = {
            "Speed": "speed",
            "RPM": "rpm",
            "Fuel": "fuel",
            "Temp": "temp",
            "Battery": "battery",
            "Steering": "steering",
            "Brake": "brake",
            "Accel": "accelerator",
            "Gear": "gear",
            "Door": "door",
            "Indicator": "indicator",
            "Headlight": "headlight",
            "EngineLoad": "engine_load",
            "AmbientTemp": "ambient_temp",
            "Odometer": "odometer",
            "WheelFL": "wheel_fl",
            "WheelFR": "wheel_fr",
            "WheelRL": "wheel_rl",
            "WheelRR": "wheel_rr",
            "BrakePressure": "brake_pressure",
            "ABS": "abs",
        }

        for serial_key, value_str in signals.items():
            # Skip metadata fields
            if serial_key in ("FrameCount", "CANActive", "Uptime", "Seq"):
                continue

            internal_name = key_mapping.get(serial_key)
            if not internal_name:
                continue

            try:
                parsed_value = self._parse_serial_value(internal_name, value_str)
                result.signals[internal_name] = parsed_value
            except (ValueError, TypeError) as e:
                result.validation_errors.append(f"{serial_key}: {e}")
                self._decode_errors += 1

        result.is_valid = len(result.validation_errors) == 0
        result.decode_time_us = (time.perf_counter() - start_time) * 1_000_000
        self._frames_decoded += 1

        return result

    def _parse_serial_value(self, signal_name: str, value_str: str) -> Any:
        """
        Parse a serial protocol value string into the appropriate type.

        Args:
            signal_name: Internal signal name
            value_str: String value from serial protocol

        Returns:
            Parsed value (float, int, or str depending on signal).
        """
        # Special cases: non-numeric signals
        if signal_name == "gear":
            return value_str  # Keep as string ("P", "R", "N", "D", etc.)

        if signal_name == "door":
            return value_str  # Keep as string ("Closed", "FL", etc.)

        # Numeric signals
        config = get_signal_config(signal_name)

        if config:
            if config.bit_length <= 1:
                return int(float(value_str))  # Boolean-like
            elif config.factor == 1.0 and config.offset == 0.0 and "." not in value_str:
                return int(value_str)  # Integer signal
            else:
                return float(value_str)  # Float signal
        else:
            # Unknown signal: try float, fall back to string
            try:
                return float(value_str)
            except ValueError:
                return value_str

    # ========================================================================
    # STATE UPDATE CONVERSION
    # ========================================================================

    def to_state_update(self, decoded: DecodedFrame) -> Dict[str, Any]:
        """
        Convert DecodedFrame to a state update dictionary
        suitable for VehicleStateManager.update_signals_batch().

        Args:
            decoded: Decoded frame

        Returns:
            Dictionary of {signal_name: value} for state manager.
        """
        update = {}

        for name, value in decoded.signals.items():
            config = get_signal_config(name)

            if config:
                # Validate and clamp
                if isinstance(value, (int, float)):
                    if not config.validate(value):
                        value = config.clamp(value)
                        self._validation_warnings += 1

            update[name] = value

        return update

    # ========================================================================
    # CONFIGURATION MANAGEMENT
    # ========================================================================

    def load_signal_configs(self, configs: Dict[str, SignalConfig]) -> None:
        """
        Load custom signal configurations (from DBC file).

        Replaces default Phase 1 configs with vehicle-specific ones.

        Args:
            configs: Dictionary of {name: SignalConfig}
        """
        self._signal_configs = configs
        self._can_id_map.clear()

        for config in configs.values():
            if config.can_id not in self._can_id_map:
                self._can_id_map[config.can_id] = []
            self._can_id_map[config.can_id].append(config)

        logger.info(f"CANFrameParser: loaded {len(configs)} custom signal configs")

    def add_signal_config(self, config: SignalConfig) -> None:
        """Add a single signal configuration."""
        self._signal_configs[config.name] = config
        if config.can_id not in self._can_id_map:
            self._can_id_map[config.can_id] = []
        self._can_id_map[config.can_id].append(config)

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get parser statistics."""
        return {
            "frames_decoded": self._frames_decoded,
            "decode_errors": self._decode_errors,
            "validation_warnings": self._validation_warnings,
            "signal_count": len(self._signal_configs),
            "can_id_count": len(self._can_id_map),
            "error_rate": (
                self._decode_errors / self._frames_decoded * 100
                if self._frames_decoded > 0 else 0
            ),
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._frames_decoded = 0
        self._decode_errors = 0
        self._validation_warnings = 0