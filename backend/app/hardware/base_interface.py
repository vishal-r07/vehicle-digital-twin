"""
============================================================================
AutoTwin AI - Abstract Hardware Interface
============================================================================
Defines the contract that ALL hardware data sources must implement.

This is the Hardware Abstraction Layer (HAL) boundary. Everything above
this layer is hardware-agnostic. Everything below is hardware-specific.

Interface Contract:
  - connect():       Establish connection to data source
  - disconnect():    Cleanly close connection
  - read():          Read next frame (async, non-blocking)
  - is_connected:    Property indicating connection state
  - get_metadata():  Source information (type, port, speed, etc.)

Implementation Requirements:
  - Must be async (asyncio-compatible)
  - Must handle reconnection gracefully
  - Must not block the event loop
  - Must emit events on connect/disconnect/error
============================================================================
"""

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger


# ============================================================================
# ENUMERATIONS
# ============================================================================


class SourceType(str, Enum):
    """Types of vehicle data sources."""

    SERIAL = "serial"           # STM32 via USB Serial
    USB_CAN = "usb_can"         # Direct USB-CAN adapter
    OBD2 = "obd2"              # OBD-II interface (Phase 2)
    SIMULATOR = "simulator"     # Software simulator
    REPLAY = "replay"           # Log file replay


class HardwareStatus(str, Enum):
    """Hardware connection status."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    CLOSED = "closed"


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class RawFrame:
    """
    Raw data frame from hardware source.

    For CAN sources: contains CAN ID + payload bytes.
    For serial sources: contains parsed key-value pairs.

    This is the universal frame format passed to the CAN Parser.
    """

    # CAN frame fields
    can_id: int = 0
    data: bytes = b""
    dlc: int = 0
    is_extended: bool = False
    timestamp_us: int = 0

    # Parsed signal data (from serial source)
    signals: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    source_type: str = "unknown"
    received_at: float = field(default_factory=time.time)
    sequence: int = 0

    @property
    def is_can_frame(self) -> bool:
        """True if this is a raw CAN frame (needs decoding)."""
        return self.can_id > 0 and len(self.data) > 0

    @property
    def is_parsed_frame(self) -> bool:
        """True if this contains pre-parsed signals (from serial)."""
        return len(self.signals) > 0

    def __repr__(self) -> str:
        if self.is_can_frame:
            return f"RawFrame(CAN ID=0x{self.can_id:03X}, DLC={self.dlc})"
        return f"RawFrame(signals={len(self.signals)} keys)"


@dataclass
class HardwareMetadata:
    """Metadata about the hardware source."""

    source_type: SourceType
    name: str
    port: str = ""
    baud_rate: int = 0
    can_baud_rate: int = 0
    firmware_version: str = ""
    connected_since: float = 0.0
    frames_received: int = 0
    errors: int = 0
    last_frame_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type.value,
            "name": self.name,
            "port": self.port,
            "baud_rate": self.baud_rate,
            "can_baud_rate": self.can_baud_rate,
            "firmware_version": self.firmware_version,
            "connected_since": self.connected_since,
            "frames_received": self.frames_received,
            "errors": self.errors,
            "last_frame_time": self.last_frame_time,
            "uptime_s": time.time() - self.connected_since if self.connected_since else 0,
        }


# ============================================================================
# ABSTRACT INTERFACE
# ============================================================================


class IHardwareSource(ABC):
    """
    Abstract interface for all vehicle data sources.

    All hardware implementations (Serial, USB-CAN, OBD-II, Simulator)
    must implement this interface.

    Lifecycle:
        source = ConcreteSource(config)
        await source.connect()
        while running:
            frame = await source.read(timeout=0.1)
            if frame: process(frame)
        await source.disconnect()
    """

    def __init__(self):
        self._status: HardwareStatus = HardwareStatus.DISCONNECTED
        self._frames_received: int = 0
        self._errors: int = 0
        self._connected_at: float = 0.0
        self._last_frame_at: float = 0.0

    # ========================================================================
    # ABSTRACT METHODS (Must be implemented by all sources)
    # ========================================================================

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the data source.

        Returns:
            True if connection successful, False otherwise.

        Raises:
            SerialConnectionError: If serial connection fails.
            CANConnectionError: If CAN connection fails.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Cleanly disconnect from the data source.
        Must be idempotent (safe to call multiple times).
        """
        ...

    @abstractmethod
    async def read(self, timeout: float = 0.1) -> Optional[RawFrame]:
        """
        Read the next frame from the source.

        Args:
            timeout: Maximum seconds to wait for a frame.

        Returns:
            RawFrame if data available, None if timeout.
        """
        ...

    @abstractmethod
    def get_metadata(self) -> HardwareMetadata:
        """
        Get source metadata and statistics.

        Returns:
            HardwareMetadata with current state.
        """
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the source is currently connected and operational."""
        ...

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        """The type of this data source."""
        ...

    # ========================================================================
    # CONCRETE METHODS (Shared by all implementations)
    # ========================================================================

    @property
    def status(self) -> HardwareStatus:
        """Current connection status."""
        return self._status

    @property
    def frames_received(self) -> int:
        """Total frames received since connection."""
        return self._frames_received

    @property
    def error_count(self) -> int:
        """Total errors encountered."""
        return self._errors

    @property
    def uptime(self) -> float:
        """Seconds since connection established."""
        if self._connected_at == 0:
            return 0.0
        return time.time() - self._connected_at

    @property
    def time_since_last_frame(self) -> float:
        """Seconds since last frame received."""
        if self._last_frame_at == 0:
            return float("inf")
        return time.time() - self._last_frame_at

    def _mark_connected(self) -> None:
        """Internal: mark as connected."""
        self._status = HardwareStatus.CONNECTED
        self._connected_at = time.time()
        logger.info(f"{self.__class__.__name__}: connected")

    def _mark_disconnected(self) -> None:
        """Internal: mark as disconnected."""
        self._status = HardwareStatus.DISCONNECTED
        logger.info(f"{self.__class__.__name__}: disconnected")

    def _mark_error(self, error_msg: str = "") -> None:
        """Internal: mark error state."""
        self._status = HardwareStatus.ERROR
        self._errors += 1
        logger.error(f"{self.__class__.__name__}: {error_msg}")

    def _record_frame(self) -> None:
        """Internal: record frame reception."""
        self._frames_received += 1
        self._last_frame_at = time.time()