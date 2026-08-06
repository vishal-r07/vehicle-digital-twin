"""
============================================================================
AutoTwin AI - CAN Bus Parsing Module
============================================================================
Handles all CAN bus data interpretation:
  - DBC file loading and validation
  - Raw frame decoding (bit extraction, factor/offset)
  - Signal metadata and definitions
  - Frame buffering for high-throughput scenarios

Data Flow:
  RawFrame → FrameParser → DecodedSignals → VehicleStateManager

Usage:
    from app.can import DBCParser, CANFrameParser, FrameBuffer

    dbc = DBCParser("vehicles/toyota/can_signals.dbc")
    parser = CANFrameParser(dbc)
    signals = parser.decode_frame(raw_frame)
============================================================================
"""

from app.can.dbc_loader import DBCParser, DBCMessage, DBCSignal  # noqa: F401
from app.can.frame_parser import CANFrameParser, DecodedFrame  # noqa: F401
from app.can.signal_definitions import (  # noqa: F401
    SignalDefinition,
    SignalConfig,
    Phase1Signals,
    get_signal_config,
)
from app.can.frame_buffer import FrameBuffer, BufferedFrame  # noqa: F401

__all__ = [
    "DBCParser",
    "DBCMessage",
    "DBCSignal",
    "CANFrameParser",
    "DecodedFrame",
    "SignalDefinition",
    "SignalConfig",
    "Phase1Signals",
    "get_signal_config",
    "FrameBuffer",
    "BufferedFrame",
]