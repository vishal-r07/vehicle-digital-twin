"""
config.py - Centralized configuration for Vehicle Digital Twin Backend

Design: All configurable parameters in one place.
Future: Load from environment variables or config file for deployment.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SerialConfig:
    """Serial port configuration for STM32 communication."""
    port: str = os.getenv("SERIAL_PORT", "COM3")  # Windows: COM3, Linux: /dev/ttyACM0
    baud_rate: int = int(os.getenv("SERIAL_BAUD", "115200"))
    timeout: float = 1.0  # seconds
    frame_start_delimiter: str = "---FRAME---"
    frame_end_delimiter: str = "---END---"


@dataclass
class WebSocketConfig:
    """WebSocket server configuration."""
    host: str = os.getenv("WS_HOST", "0.0.0.0")
    port: int = int(os.getenv("WS_PORT", "8765"))
    ping_interval: float = 20.0
    ping_timeout: float = 10.0


@dataclass
class VehicleConfig:
    """Vehicle signal thresholds and limits."""
    speed_max: float = 300.0       # km/h
    rpm_max: int = 8000
    rpm_redline: int = 6500
    fuel_low_threshold: float = 15.0   # %
    temp_high_threshold: int = 105     # °C
    temp_critical_threshold: int = 120  # °C
    battery_low_threshold: float = 11.5  # V
    steering_max: float = 720.0    # degrees


@dataclass
class AppConfig:
    """Master application configuration."""
    serial: SerialConfig = field(default_factory=SerialConfig)
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    vehicle: VehicleConfig = field(default_factory=VehicleConfig)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    broadcast_interval_ms: int = 50  # 20 Hz update rate


# Singleton configuration instance
config = AppConfig()