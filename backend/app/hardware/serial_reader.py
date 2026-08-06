"""
============================================================================
AutoTwin AI - STM32 USB Serial Reader
============================================================================
Reads structured vehicle data from STM32F103RB over USB Serial (CDC).

Protocol:
  The STM32 firmware outputs frames delimited by:
    ---AUTOTWIN---
    Speed=58.00
    RPM=2450
    ...
    ---END---

  This reader:
    1. Connects to the serial port
    2. Reads lines continuously in a background thread
    3. Extracts frames between delimiters
    4. Parses key=value pairs into dictionaries
    5. Pushes parsed frames to an asyncio queue
    6. Handles reconnection on failure

Thread Model:
  - Serial reading runs in a dedicated thread (blocking I/O)
  - Frame queue bridges thread → asyncio event loop
  - Main async code reads from the queue without blocking

Usage:
    reader = SerialReader(settings.serial, event_bus)
    await reader.start()

    # In main loop:
    frame = await reader.read(timeout=0.1)
    if frame:
        process(frame.signals)

    await reader.stop()
============================================================================
"""

import asyncio
import queue
import threading
import time
from typing import Any, Dict, Optional

import serial
import serial.tools.list_ports
from loguru import logger

from app.config import SerialSettings
from app.core.constants import EventType
from app.core.event_bus import EventBus
from app.core.exceptions import SerialConnectionError
from app.hardware.base_interface import (
    HardwareMetadata,
    HardwareStatus,
    IHardwareSource,
    RawFrame,
    SourceType,
)


# ============================================================================
# SERIAL READER IMPLEMENTATION
# ============================================================================


class SerialReader(IHardwareSource):
    """
    Reads vehicle data from STM32 via USB Serial.

    Features:
      - Auto-detect STM32 port
      - Automatic reconnection
      - Frame extraction and parsing
      - Thread-safe async interface
      - Connection state events
      - Rate monitoring
    """

    def __init__(self, settings: SerialSettings, event_bus: EventBus):
        super().__init__()
        self._settings = settings
        self._event_bus = event_bus

        # Serial connection
        self._port: Optional[serial.Serial] = None
        self._port_name: str = settings.port

        # Threading
        self._read_thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._thread_lock = threading.Lock()

        # Frame queue (thread → asyncio bridge)
        self._frame_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._raw_queue: queue.Queue = queue.Queue(maxsize=200)

        # Statistics
        self._frames_parsed: int = 0
        self._frames_dropped: int = 0
        self._parse_errors: int = 0
        self._reconnect_count: int = 0
        self._last_frame_time: float = 0.0
        self._frame_rate: float = 0.0  # Calculated FPS

    # ========================================================================
    # IHardwareSource INTERFACE
    # ========================================================================

    @property
    def source_type(self) -> SourceType:
        return SourceType.SERIAL

    @property
    def is_connected(self) -> bool:
        return self._status == HardwareStatus.CONNECTED and self._running

    async def connect(self) -> bool:
        """Connect to STM32 serial port."""
        self._status = HardwareStatus.CONNECTING

        try:
            port_name = self._find_port()
            self._port_name = port_name

            self._port = serial.Serial(
                port=port_name,
                baudrate=self._settings.baud_rate,
                timeout=self._settings.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                write_timeout=1.0,
            )

            # Flush startup garbage
            time.sleep(0.5)
            self._port.reset_input_buffer()
            self._port.reset_output_buffer()

            self._mark_connected()

            # Emit connection event
            await self._event_bus.publish(
                EventType.SERIAL_CONNECTED,
                data={"port": port_name, "baud_rate": self._settings.baud_rate},
                source="serial_reader",
            )

            return True

        except serial.SerialException as e:
            self._mark_error(f"Connection failed: {e}")
            raise SerialConnectionError(
                port=self._settings.port,
                reason=str(e),
            )

    async def disconnect(self) -> None:
        """Disconnect from serial port."""
        self._running = False

        # Stop read thread
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join(timeout=3.0)

        # Close serial port
        if self._port and self._port.is_open:
            self._port.close()
            self._port = None

        self._mark_disconnected()

        await self._event_bus.publish(
            EventType.SERIAL_DISCONNECTED,
            data={"port": self._port_name, "frames_received": self._frames_received},
            source="serial_reader",
        )

    async def read(self, timeout: float = 0.1) -> Optional[RawFrame]:
        """Read next parsed frame from the queue."""
        try:
            frame = await asyncio.wait_for(self._frame_queue.get(), timeout=timeout)
            return frame
        except asyncio.TimeoutError:
            return None

    def get_metadata(self) -> HardwareMetadata:
        """Get serial reader metadata and statistics."""
        return HardwareMetadata(
            source_type=SourceType.SERIAL,
            name="STM32F103RB USB Serial",
            port=self._port_name,
            baud_rate=self._settings.baud_rate,
            can_baud_rate=500000,
            connected_since=self._connected_at,
            frames_received=self._frames_received,
            errors=self._errors,
            last_frame_time=self._last_frame_at,
        )

    # ========================================================================
    # LIFECYCLE MANAGEMENT
    # ========================================================================

    async def start(self) -> None:
        """Start the serial reader (connect + background thread)."""
        if self._running:
            logger.warning("SerialReader: already running")
            return

        # Connect
        await self.connect()

        # Start background read thread
        self._running = True
        self._read_thread = threading.Thread(
            target=self._serial_read_loop,
            name="serial-reader",
            daemon=True,
        )
        self._read_thread.start()

        # Start async queue consumer
        asyncio.create_task(self._queue_consumer())

        logger.info(f"SerialReader: started on {self._port_name}")

    async def stop(self) -> None:
        """Stop the serial reader completely."""
        await self.disconnect()
        logger.info("SerialReader: stopped")

    # ========================================================================
    # PORT DETECTION
    # ========================================================================

    def _find_port(self) -> str:
        """
        Auto-detect STM32 Nucleo serial port.

        Search order:
          1. STMicroelectronics device (ST-Link VCP)
          2. ttyACM* (Linux CDC ACM)
          3. Configured port (fallback)
        """
        if not self._settings.auto_detect:
            return self._settings.port

        ports = serial.tools.list_ports.comports()

        # Priority 1: STMicroelectronics (ST-Link)
        for port in ports:
            if "STMicro" in port.description or "ST-LINK" in port.description:
                logger.info(f"SerialReader: found STM32 on {port.device} ({port.description})")
                return port.device

        # Priority 2: ttyACM (Linux)
        for port in ports:
            if "ttyACM" in port.device or "ttyUSB" in port.device:
                logger.info(f"SerialReader: found potential STM32 on {port.device}")
                return port.device

        # Priority 3: COM ports (Windows)
        for port in ports:
            if "COM" in port.device and "USB" in port.description:
                logger.info(f"SerialReader: found USB serial on {port.device}")
                return port.device

        # Fallback: configured port
        logger.warning(
            f"SerialReader: no STM32 auto-detected, using configured port: "
            f"{self._settings.port}"
        )
        return self._settings.port

    # ========================================================================
    # BACKGROUND SERIAL READ THREAD
    # ========================================================================

    def _serial_read_loop(self) -> None:
        """
        Background thread: continuously read serial data.

        This runs in a separate thread because serial I/O is blocking.
        Parsed frames are pushed to a thread-safe queue.
        """
        buffer_lines: list = []
        in_frame: bool = False
        frame_start = self._settings.frame_start_token
        frame_end = self._settings.frame_end_token

        while self._running:
            try:
                # Check connection
                if not self._port or not self._port.is_open:
                    logger.warning("SerialReader: port lost, attempting reconnect...")
                    self._attempt_reconnect()
                    continue

                # Read available data
                if self._port.in_waiting > 0:
                    line = self._port.readline().decode("utf-8", errors="ignore").strip()

                    if not line:
                        continue

                    # Frame start delimiter
                    if line == frame_start:
                        in_frame = True
                        buffer_lines = []
                        continue

                    # Frame end delimiter
                    if line == frame_end:
                        if in_frame and buffer_lines:
                            # Parse the complete frame
                            parsed = self._parse_frame_lines(buffer_lines)
                            if parsed:
                                self._raw_queue.put_nowait(parsed)
                        in_frame = False
                        buffer_lines = []
                        continue

                    # Accumulate lines within frame
                    if in_frame:
                        buffer_lines.append(line)

                else:
                    # No data available, small sleep to prevent CPU spinning
                    time.sleep(0.001)

            except serial.SerialException as e:
                if self._running:
                    logger.error(f"SerialReader: read error: {e}")
                    self._errors += 1
                    time.sleep(1.0)
                    self._attempt_reconnect()

            except Exception as e:
                if self._running:
                    logger.error(f"SerialReader: unexpected error: {e}")
                    time.sleep(0.5)

    def _attempt_reconnect(self) -> None:
        """Attempt to reconnect to serial port."""
        self._status = HardwareStatus.RECONNECTING
        self._reconnect_count += 1

        if self._reconnect_count > self._settings.max_reconnect_attempts:
            logger.error("SerialReader: max reconnection attempts reached")
            self._status = HardwareStatus.ERROR
            return

        # Close existing port
        if self._port and self._port.is_open:
            try:
                self._port.close()
            except Exception:
                pass

        time.sleep(self._settings.reconnect_interval)

        try:
            self._port = serial.Serial(
                port=self._port_name,
                baudrate=self._settings.baud_rate,
                timeout=self._settings.timeout,
            )
            time.sleep(0.3)
            self._port.reset_input_buffer()
            self._status = HardwareStatus.CONNECTED
            logger.info(f"SerialReader: reconnected to {self._port_name}")
        except serial.SerialException as e:
            logger.warning(f"SerialReader: reconnect failed: {e}")

    # ========================================================================
    # FRAME PARSING
    # ========================================================================

    def _parse_frame_lines(self, lines: list) -> Optional[Dict[str, Any]]:
        """
        Parse key=value lines into a dictionary.

        Input:  ["Speed=58.00", "RPM=2450", "Fuel=82.0", ...]
        Output: {"Speed": "58.00", "RPM": "2450", "Fuel": "82.0", ...}
        """
        parsed = {}

        for line in lines:
            if "=" not in line:
                continue

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            if key and value:
                parsed[key] = value

        if not parsed:
            self._parse_errors += 1
            return None

        self._frames_parsed += 1
        return parsed

    # ========================================================================
    # ASYNC QUEUE CONSUMER
    # ========================================================================

    async def _queue_consumer(self) -> None:
        """
        Async task: consume frames from thread queue and push to async queue.

        Bridges the threading.Queue (written by serial thread) to
        asyncio.Queue (read by main async code).
        """
        while self._running:
            try:
                # Non-blocking check of thread queue
                try:
                    raw_data = self._raw_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.005)
                    continue

                # Convert to RawFrame
                frame = RawFrame(
                    signals=raw_data,
                    source_type="serial",
                    received_at=time.time(),
                    sequence=self._frames_received,
                )

                # Push to async queue
                try:
                    self._frame_queue.put_nowait(frame)
                    self._record_frame()
                except asyncio.QueueFull:
                    self._frames_dropped += 1
                    logger.warning("SerialReader: frame queue full, dropping frame")

            except Exception as e:
                logger.error(f"SerialReader: queue consumer error: {e}")
                await asyncio.sleep(0.1)

    # ========================================================================
    # STATISTICS & MONITORING
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get detailed serial reader statistics."""
        return {
            "port": self._port_name,
            "baud_rate": self._settings.baud_rate,
            "status": self._status.value,
            "connected": self.is_connected,
            "frames_received": self._frames_received,
            "frames_parsed": self._frames_parsed,
            "frames_dropped": self._frames_dropped,
            "parse_errors": self._parse_errors,
            "reconnect_count": self._reconnect_count,
            "queue_size": self._frame_queue.qsize(),
            "uptime_s": self.uptime,
            "time_since_last_frame_s": self.time_since_last_frame,
        }

    @property
    def frame_rate(self) -> float:
        """Estimated frames per second."""
        if self._frames_received < 2:
            return 0.0
        uptime = self.uptime
        return self._frames_received / uptime if uptime > 0 else 0.0