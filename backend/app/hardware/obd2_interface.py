"""
============================================================================
AutoTwin AI - OBD-II Interface (Phase 2 - STUB)
============================================================================
Placeholder for OBD-II vehicle interface.

Phase 2 Implementation Plan:
  - Support ELM327 USB/Bluetooth adapters
  - Support J2534 Pass-Thru devices
  - OBD-II PID polling (Mode 01)
  - DTC reading (Mode 03) and clearing (Mode 04)
  - Enhanced diagnostics (Mode 06, 09)
  - UDS services (ISO 14229) for manufacturer-specific data

OBD-II PIDs to Support (Phase 2):
  0x0C - Engine RPM
  0x0D - Vehicle Speed
  0x05 - Coolant Temperature
  0x42 - Control Module Voltage
  0x0F - Intake Air Temperature
  0x10 - MAF Air Flow Rate
  0x11 - Throttle Position
  0x0E - Timing Advance
  0x1F - Run Time Since Start

Dependencies (Phase 2):
  pip install python-obd
  # or
  pip install obd2

NOTE: This file is a STUB. It defines the interface but does NOT
implement functionality. Implementation begins in Phase 2.
============================================================================
"""

import asyncio
from typing import Any, Dict, Optional

from loguru import logger

from app.core.event_bus import EventBus
from app.hardware.base_interface import (
    HardwareMetadata,
    HardwareStatus,
    IHardwareSource,
    RawFrame,
    SourceType,
)


# ============================================================================
# OBD-II PID DEFINITIONS (Phase 2 Reference)
# ============================================================================

OBD2_PIDS = {
    0x0C: {"name": "engine_rpm", "formula": "(A*256+B)/4", "unit": "rpm", "min": 0, "max": 16383},
    0x0D: {"name": "vehicle_speed", "formula": "A", "unit": "km/h", "min": 0, "max": 255},
    0x05: {"name": "coolant_temp", "formula": "A-40", "unit": "°C", "min": -40, "max": 215},
    0x42: {"name": "battery_voltage", "formula": "(A*256+B)/1000", "unit": "V", "min": 0, "max": 65},
    0x0F: {"name": "intake_air_temp", "formula": "A-40", "unit": "°C", "min": -40, "max": 215},
    0x10: {"name": "maf_flow_rate", "formula": "(A*256+B)/100", "unit": "g/s", "min": 0, "max": 655},
    0x11: {"name": "throttle_position", "formula": "A*100/255", "unit": "%", "min": 0, "max": 100},
    0x0E: {"name": "timing_advance", "formula": "A/2-64", "unit": "°", "min": -64, "max": 63},
    0x1F: {"name": "run_time", "formula": "A*256+B", "unit": "s", "min": 0, "max": 65535},
    0x2F: {"name": "fuel_level", "formula": "A*100/255", "unit": "%", "min": 0, "max": 100},
    0x46: {"name": "ambient_temp", "formula": "A-40", "unit": "°C", "min": -40, "max": 215},
    0x04: {"name": "engine_load", "formula": "A*100/255", "unit": "%", "min": 0, "max": 100},
}


# ============================================================================
# OBD-II INTERFACE (STUB - Phase 2)
# ============================================================================


class OBD2Interface(IHardwareSource):
    """
    OBD-II vehicle interface.

    STATUS: NOT IMPLEMENTED (Phase 2)

    This class defines the interface for OBD-II communication.
    Implementation will support:
      - ELM327 USB adapters (serial protocol)
      - ELM327 Bluetooth adapters
      - J2534 Pass-Thru devices
      - Direct CAN via OBD-II connector

    OBD-II Connector Pinout (16-pin DLC):
      Pin 4:  Chassis Ground
      Pin 5:  Signal Ground
      Pin 6:  CAN High (ISO 15765-4)
      Pin 14: CAN Low (ISO 15765-4)
      Pin 16: Battery Power (+12V)
    """

    def __init__(self, event_bus: EventBus, port: str = "AUTO"):
        super().__init__()
        self._event_bus = event_bus
        self._port = port
        self._protocol: str = ""  # Auto-detected protocol
        self._vin: str = ""  # Vehicle Identification Number
        self._supported_pids: list = []

        logger.warning("OBD2Interface: STUB - not yet implemented (Phase 2)")

    @property
    def source_type(self) -> SourceType:
        return SourceType.OBD2

    @property
    def is_connected(self) -> bool:
        return False  # Not implemented

    async def connect(self) -> bool:
        """
        Connect to OBD-II adapter.

        Phase 2 Implementation:
          1. Scan for ELM327 devices (serial/Bluetooth)
          2. Send AT commands to initialize
          3. Detect protocol (CAN 11-bit, CAN 29-bit, etc.)
          4. Query supported PIDs
          5. Read VIN (Mode 09, PID 02)
        """
        logger.error("OBD2Interface.connect(): NOT IMPLEMENTED (Phase 2)")
        raise NotImplementedError("OBD-II support is planned for Phase 2")

    async def disconnect(self) -> None:
        """Disconnect from OBD-II adapter."""
        logger.warning("OBD2Interface.disconnect(): NOT IMPLEMENTED")
        self._mark_disconnected()

    async def read(self, timeout: float = 0.1) -> Optional[RawFrame]:
        """
        Read OBD-II data.

        Phase 2 Implementation:
          - Poll supported PIDs in round-robin
          - Decode responses using PID formulas
          - Package as RawFrame with signals dict
        """
        return None  # Not implemented

    def get_metadata(self) -> HardwareMetadata:
        return HardwareMetadata(
            source_type=SourceType.OBD2,
            name="OBD-II Interface (Not Implemented)",
            port=self._port,
            baud_rate=0,
            can_baud_rate=500000,
        )

    # ========================================================================
    # PHASE 2 METHODS (Defined but not implemented)
    # ========================================================================

    async def read_dtc(self) -> list:
        """
        Read Diagnostic Trouble Codes (Mode 03).

        Returns:
            List of DTC strings (e.g., ["P0128", "P0420"])
        """
        raise NotImplementedError("Phase 2")

    async def clear_dtc(self) -> bool:
        """
        Clear Diagnostic Trouble Codes (Mode 04).

        Returns:
            True if codes cleared successfully.
        """
        raise NotImplementedError("Phase 2")

    async def read_pid(self, pid: int) -> float:
        """
        Read a single OBD-II PID value.

        Args:
            pid: PID number (e.g., 0x0C for RPM)

        Returns:
            Decoded physical value.
        """
        raise NotImplementedError("Phase 2")

    async def get_supported_pids(self) -> list:
        """
        Query which PIDs the vehicle supports (Mode 01, PID 00/20/40).

        Returns:
            List of supported PID numbers.
        """
        raise NotImplementedError("Phase 2")

    async def get_vin(self) -> str:
        """
        Read Vehicle Identification Number (Mode 09, PID 02).

        Returns:
            17-character VIN string.
        """
        raise NotImplementedError("Phase 2")