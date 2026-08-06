"""
============================================================================
AutoTwin AI - Hardware Abstraction Layer
============================================================================
Provides a unified interface for all vehicle data sources.

Supported Sources (Phase 1):
  - SerialReader:    STM32F103RB + MCP2515 via USB Serial
  - Simulator:       Software-generated CAN data (no hardware needed)

Supported Sources (Phase 2+):
  - USBCANSource:    Direct USB-CAN adapter (python-can)
  - OBD2Interface:   OBD-II via ELM327 or J2534

Design Principle:
  All upper layers (CAN Parser, State Manager, Diagnostics) interact
  ONLY with the IHardwareSource interface. Swapping hardware requires
  ZERO changes to application logic.

Usage:
    from app.hardware import create_source, SourceType

    source = create_source(SourceType.SERIAL, config)
    await source.connect()
    frame = await source.read()
============================================================================
"""

from app.hardware.base_interface import (  # noqa: F401
    IHardwareSource,
    HardwareStatus,
    SourceType,
    RawFrame,
)
from app.hardware.serial_reader import SerialReader  # noqa: F401
from app.hardware.can_source import CANSourceManager, create_source  # noqa: F401
from app.hardware.simulator import CANSimulator  # noqa: F401

__all__ = [
    "IHardwareSource",
    "HardwareStatus",
    "SourceType",
    "RawFrame",
    "SerialReader",
    "CANSourceManager",
    "create_source",
    "CANSimulator",
]