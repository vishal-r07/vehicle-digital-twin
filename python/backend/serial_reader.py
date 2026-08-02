"""
serial_reader.py - STM32 Serial Port Reader

Reads structured data from STM32 Nucleo over USB Serial.
Handles reconnection, buffering, and frame extraction.

Future: Support multiple serial ports (multi-ECU), TCP serial bridges.
"""

import serial
import serial.tools.list_ports
import threading
import queue
import time
from typing import Optional

from .config import config
from .utils.logger import setup_logger

logger = setup_logger("SerialReader")


class SerialReader:
    """
    Reads structured frames from STM32 serial output.
    
    Protocol:
        ---FRAME---
        Speed=58.00
        RPM=2450
        ...
        ---END---
    
    Thread-safe: Runs in a background thread, pushes frames to a queue.
    """
    
    def __init__(self):
        self._port: Optional[serial.Serial] = None
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._frame_queue: queue.Queue = queue.Queue(maxsize=100)
        self._config = config.serial
        self._connected: bool = False
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    def find_port(self) -> Optional[str]:
        """Auto-detect STM32 Nucleo serial port."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # STM32 Nucleo typically shows as STMicroelectronics
            if 'STMicro' in port.description or 'ST-LINK' in port.description:
                logger.info(f"Found STM32 Nucleo on {port.device}: {port.description}")
                return port.device
            # Fallback: common ACM ports on Linux
            if 'ttyACM' in port.device:
                logger.info(f"Found potential STM32 on {port.device}")
                return port.device
        
        logger.warning(f"No STM32 found. Using configured port: {self._config.port}")
        return self._config.port
    
    def connect(self) -> bool:
        """Establish serial connection to STM32."""
        try:
            port = self.find_port()
            self._port = serial.Serial(
                port=port,
                baudrate=self._config.baud_rate,
                timeout=self._config.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            self._connected = True
            logger.info(f"Connected to {port} at {self._config.baud_rate} baud")
            
            # Flush any startup garbage
            time.sleep(0.5)
            self._port.reset_input_buffer()
            return True
            
        except serial.SerialException as e:
            logger.error(f"Serial connection failed: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Close serial connection."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._port and self._port.is_open:
            self._port.close()
        self._connected = False
        logger.info("Serial connection closed")
    
    def start(self):
        """Start background reading thread."""
        if not self._connected:
            if not self.connect():
                logger.error("Cannot start reader - no connection")
                return
        
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info("Serial reader thread started")
    
    def stop(self):
        """Stop background reading thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("Serial reader thread stopped")
    
    def get_frame(self, timeout: float = 0.1) -> Optional[dict]:
        """Get next parsed frame from queue (non-blocking with timeout)."""
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def _read_loop(self):
        """Background thread: continuously read and parse serial data."""
        buffer = ""
        in_frame = False
        frame_data = {}
        
        while self._running:
            try:
                if not self._port or not self._port.is_open:
                    logger.warning("Serial port lost. Attempting reconnection...")
                    time.sleep(2.0)
                    self.connect()
                    continue
                
                if self._port.in_waiting > 0:
                    line = self._port.readline().decode('utf-8', errors='ignore').strip()
                    
                    if not line:
                        continue
                    
                    # Frame start delimiter
                    if line == self._config.frame_start_delimiter:
                        in_frame = True
                        frame_data = {}
                        continue
                    
                    # Frame end delimiter
                    if line == self._config.frame_end_delimiter:
                        if in_frame and frame_data:
                            # Push complete frame to queue
                            try:
                                self._frame_queue.put_nowait(frame_data.copy())
                            except queue.Full:
                                # Drop oldest frame if queue is full
                                try:
                                    self._frame_queue.get_nowait()
                                    self._frame_queue.put_nowait(frame_data.copy())
                                except queue.Empty:
                                    pass
                        
                        in_frame = False
                        frame_data = {}
                        continue
                    
                    # Parse key=value pairs within frame
                    if in_frame and '=' in line:
                        key, _, value = line.partition('=')
                        frame_data[key.strip()] = value.strip()
                
                else:
                    time.sleep(0.001)  # Prevent CPU spinning
                    
            except serial.SerialException as e:
                logger.error(f"Serial read error: {e}")
                self._connected = False
                time.sleep(2.0)
                self.connect()
                
            except Exception as e:
                logger.error(f"Unexpected error in read loop: {e}")
                time.sleep(1.0)