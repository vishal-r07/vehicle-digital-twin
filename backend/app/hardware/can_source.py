"""
============================================================================
AutoTwin AI - Unified CAN Source Manager
============================================================================
Manages the active hardware source and provides a single interface
for the rest of the application.

This is the SINGLE ENTRY POINT for all vehicle data.
Upper layers never interact with SerialReader/CANSimulator directly.

Responsibilities:
  - Source selection and lifecycle
  - Source switching (live → simulator → replay)
  - Health monitoring of the active source
  - Timeout detection
  - Event emission on source changes

Usage:
    manager = CANSourceManager(event_bus, settings)

    # Start with serial source
    await manager.start(SourceType.SERIAL)

    # Read frames (regardless of source type)
    frame = await manager.read(timeout=0.1)

    # Switch to simulator
    await manager.switch_source(SourceType.SIMULATOR)
============================================================================
"""

import asyncio
import time
from typing import Dict, Optional

from loguru import logger

from app.config import Settings
from app.core.constants import EventType, DataSource, SystemStatus
from app.core.event_bus import EventBus
from app.hardware.base_interface import (
    HardwareMetadata,
    HardwareStatus,
    IHardwareSource,
    RawFrame,
    SourceType,
)
from app.hardware.serial_reader import SerialReader
from app.hardware.simulator import CANSimulator


# ============================================================================
# CAN SOURCE MANAGER
# ============================================================================


class CANSourceManager:
    """
    Manages the active vehicle data source.

    Provides a unified interface regardless of whether data comes from:
      - STM32 serial
      - USB-CAN adapter
      - Software simulator
      - Replay engine

    Only ONE source is active at a time.
    """

    def __init__(self, event_bus: EventBus, settings: Settings):
        self._event_bus = event_bus
        self._settings = settings

        # Active source
        self._active_source: Optional[IHardwareSource] = None
        self._active_type: Optional[SourceType] = None
        self._status: SystemStatus = SystemStatus.INITIALIZING

        # Available sources (lazy-initialized)
        self._sources: Dict[SourceType, IHardwareSource] = {}

        # Monitoring
        self._monitor_task: Optional[asyncio.Task] = None
        self._running: bool = False

        # Statistics
        self._total_frames: int = 0
        self._source_switches: int = 0

    # ========================================================================
    # SOURCE MANAGEMENT
    # ========================================================================

    async def start(self, source_type: SourceType = SourceType.SERIAL) -> bool:
        """
        Start the specified data source.

        Args:
            source_type: Which source to activate.

        Returns:
            True if source started successfully.
        """
        logger.info(f"CANSourceManager: starting source '{source_type.value}'")

        # Create source if not already created
        source = self._get_or_create_source(source_type)
        if source is None:
            logger.error(f"CANSourceManager: cannot create source '{source_type.value}'")
            return False

        # Connect
        try:
            success = await source.connect()
            if not success:
                return False
        except Exception as e:
            logger.error(f"CANSourceManager: connection failed: {e}")
            return False

        # Set as active
        self._active_source = source
        self._active_type = source_type
        self._status = SystemStatus.RUNNING
        self._running = True

        # Start monitoring task
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info(f"CANSourceManager: source '{source_type.value}' active")
        return True

    async def stop(self) -> None:
        """Stop the active source and cleanup."""
        self._running = False

        # Cancel monitor task
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Disconnect active source
        if self._active_source:
            await self._active_source.disconnect()
            self._active_source = None
            self._active_type = None

        self._status = SystemStatus.SHUTTING_DOWN
        logger.info("CANSourceManager: stopped")

    async def switch_source(self, new_type: SourceType) -> bool:
        """
        Switch to a different data source.

        Disconnects current source and connects new one.

        Args:
            new_type: The source type to switch to.

        Returns:
            True if switch successful.
        """
        if new_type == self._active_type:
            logger.warning(f"CANSourceManager: already using '{new_type.value}'")
            return True

        logger.info(
            f"CANSourceManager: switching "
            f"'{self._active_type.value if self._active_type else 'none'}' → '{new_type.value}'"
        )

        # Stop current source
        if self._active_source:
            await self._active_source.disconnect()
            self._active_source = None

        # Start new source
        success = await self.start(new_type)
        if success:
            self._source_switches += 1
            await self._event_bus.publish(
                EventType.VEHICLE_SELECTED,
                data={"source": new_type.value},
                source="can_source_manager",
            )

        return success

    # ========================================================================
    # DATA READING
    # ========================================================================

    async def read(self, timeout: float = 0.1) -> Optional[RawFrame]:
        """
        Read next frame from the active source.

        This is the ONLY method upper layers need to call.

        Args:
            timeout: Maximum wait time in seconds.

        Returns:
            RawFrame or None if timeout.
        """
        if not self._active_source or not self._active_source.is_connected:
            return None

        frame = await self._active_source.read(timeout=timeout)
        if frame:
            self._total_frames += 1
        return frame

    # ========================================================================
    # SOURCE FACTORY
    # ========================================================================

    def _get_or_create_source(self, source_type: SourceType) -> Optional[IHardwareSource]:
        """Get existing source or create a new one."""
        if source_type in self._sources:
            return self._sources[source_type]

        source = None

        if source_type == SourceType.SERIAL:
            source = SerialReader(self._settings.serial, self._event_bus)

        elif source_type == SourceType.SIMULATOR:
            source = CANSimulator(self._event_bus)

        elif source_type == SourceType.USB_CAN:
            # Phase 2: Direct USB-CAN adapter
            logger.warning("USB_CAN source not yet implemented (Phase 2)")
            return None

        elif source_type == SourceType.OBD2:
            # Phase 2: OBD-II
            logger.warning("OBD2 source not yet implemented (Phase 2)")
            return None

        elif source_type == SourceType.REPLAY:
            # Phase 1.5: Replay engine
            logger.warning("REPLAY source not yet implemented")
            return None

        if source:
            self._sources[source_type] = source

        return source

    # ========================================================================
    # MONITORING
    # ========================================================================

    async def _monitor_loop(self) -> None:
        """Background task: monitor source health."""
        while self._running:
            try:
                await asyncio.sleep(5.0)  # Check every 5 seconds

                if self._active_source:
                    # Check for timeout
                    time_since_frame = self._active_source.time_since_last_frame
                    timeout_s = self._settings.can.timeout_ms / 1000.0

                    if time_since_frame > timeout_s and self._active_source.is_connected:
                        logger.warning(
                            f"CANSourceManager: no data for {time_since_frame:.1f}s "
                            f"(timeout={timeout_s}s)"
                        )
                        await self._event_bus.publish(
                            EventType.CAN_TIMEOUT,
                            data={
                                "time_since_last_frame_s": time_since_frame,
                                "timeout_s": timeout_s,
                                "source": self._active_type.value if self._active_type else "unknown",
                            },
                            source="can_source_manager",
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"CANSourceManager: monitor error: {e}")

    # ========================================================================
    # PROPERTIES & STATISTICS
    # ========================================================================

    @property
    def active_source_type(self) -> Optional[SourceType]:
        return self._active_type

    @property
    def is_active(self) -> bool:
        return self._active_source is not None and self._active_source.is_connected

    @property
    def status(self) -> SystemStatus:
        return self._status

    def get_metadata(self) -> Optional[HardwareMetadata]:
        """Get active source metadata."""
        if self._active_source:
            return self._active_source.get_metadata()
        return None

    def get_stats(self) -> Dict:
        """Get source manager statistics."""
        return {
            "active_source": self._active_type.value if self._active_type else None,
            "status": self._status.value,
            "is_active": self.is_active,
            "total_frames": self._total_frames,
            "source_switches": self._source_switches,
            "source_metadata": self.get_metadata().to_dict() if self.get_metadata() else None,
        }


# ============================================================================
# FACTORY FUNCTION
# ============================================================================


def create_source(source_type: SourceType, settings: Settings, event_bus: EventBus) -> IHardwareSource:
    """
    Factory function to create a hardware source.

    Args:
        source_type: Type of source to create.
        settings: Application settings.
        event_bus: Event bus for connection events.

    Returns:
        Configured IHardwareSource instance.

    Raises:
        ValueError: If source type is not supported.
    """
    if source_type == SourceType.SERIAL:
        return SerialReader(settings.serial, event_bus)
    elif source_type == SourceType.SIMULATOR:
        return CANSimulator(event_bus)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")