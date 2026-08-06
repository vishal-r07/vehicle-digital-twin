"""
============================================================================
AutoTwin AI - Configuration Management
============================================================================
Centralized configuration using Pydantic Settings.

Configuration is loaded from:
  1. Environment variables (highest priority)
  2. .env file in project root
  3. Default values defined here

Usage:
    from app.config import get_settings
    settings = get_settings()
    print(settings.server.port)
    print(settings.serial.port)

Environment Variable Naming Convention:
    Nested settings use double underscore:
    SERVER_PORT=8000
    SERIAL_PORT=COM3
    DATABASE_URL=sqlite:///./autotwin.db
============================================================================
"""

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================================
# APPLICATION SETTINGS
# ============================================================================


class AppSettings(BaseSettings):
    """Core application settings."""

    model_config = SettingsConfigDict(env_prefix="APP_")

    name: str = "AutoTwin AI"
    version: str = "1.0.0"
    description: str = (
        "Real-Time Vehicle Digital Twin & Intelligent Diagnostic Platform"
    )
    debug: bool = False
    log_level: str = "INFO"
    environment: str = "development"  # development, staging, production


# ============================================================================
# SERVER SETTINGS
# ============================================================================


class ServerSettings(BaseSettings):
    """HTTP/WebSocket server configuration."""

    model_config = SettingsConfigDict(env_prefix="SERVER_")

    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    workers: int = 1
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


# ============================================================================
# SERIAL / HARDWARE SETTINGS
# ============================================================================


class SerialSettings(BaseSettings):
    """STM32 USB Serial communication settings."""

    model_config = SettingsConfigDict(env_prefix="SERIAL_")

    port: str = "COM3"  # Windows: COM3, Linux: /dev/ttyACM0
    baud_rate: int = 115200
    timeout: float = 1.0  # seconds
    reconnect_interval: float = 2.0  # seconds between reconnection attempts
    max_reconnect_attempts: int = 50
    read_buffer_size: int = 4096
    frame_start_token: str = "---AUTOTWIN---"
    frame_end_token: str = "---END---"
    auto_detect: bool = True  # Auto-detect STM32 port

    @field_validator("baud_rate")
    @classmethod
    def validate_baud_rate(cls, v: int) -> int:
        valid_rates = {9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600}
        if v not in valid_rates:
            raise ValueError(f"Baud rate must be one of {valid_rates}")
        return v


# ============================================================================
# CAN BUS SETTINGS
# ============================================================================


class CANSettings(BaseSettings):
    """CAN bus configuration."""

    model_config = SettingsConfigDict(env_prefix="CAN_")

    baud_rate: int = 500000
    buffer_size: int = 1000  # Ring buffer capacity
    timeout_ms: int = 2000  # No-data timeout
    id_min: int = 0x100
    id_max: int = 0x10F
    log_frames: bool = False  # Log raw CAN frames to DB


# ============================================================================
# DATABASE SETTINGS
# ============================================================================


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = "sqlite:///./autotwin.db"
    echo: bool = False  # Log SQL queries
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30

    @property
    def async_url(self) -> str:
        """Get async-compatible URL."""
        if self.url.startswith("sqlite:///"):
            return self.url.replace("sqlite:///", "sqlite+aiosqlite:///")
        elif self.url.startswith("postgresql://"):
            return self.url.replace("postgresql://", "postgresql+asyncpg://")
        return self.url

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.url


# ============================================================================
# WEBSOCKET SETTINGS
# ============================================================================


class WebSocketSettings(BaseSettings):
    """WebSocket broadcast configuration."""

    model_config = SettingsConfigDict(env_prefix="WS_")

    heartbeat_interval: float = 20.0  # seconds
    ping_timeout: float = 10.0  # seconds
    max_connections: int = 50
    max_message_size: int = 65536  # 64 KB
    compression: bool = False


# ============================================================================
# BROADCAST SETTINGS
# ============================================================================


class BroadcastSettings(BaseSettings):
    """State broadcast configuration."""

    model_config = SettingsConfigDict(env_prefix="BROADCAST_")

    interval_ms: int = 50  # 20 Hz
    include_timestamp: bool = True
    include_metadata: bool = True
    delta_only: bool = False  # Only send changed fields (future)
    max_queue_size: int = 100


# ============================================================================
# DIAGNOSTICS SETTINGS
# ============================================================================


class DiagnosticsSettings(BaseSettings):
    """Fault detection and health scoring configuration."""

    model_config = SettingsConfigDict(env_prefix="DIAG_")

    fault_cooldown_s: int = 30  # Seconds before fault can re-trigger
    health_update_interval_s: int = 10
    timeline_max_events: int = 10000
    health_history_max: int = 1000
    debounce_default_ms: int = 3000
    confidence_threshold: float = 0.6  # Minimum confidence to report


# ============================================================================
# VEHICLE PLUGIN SETTINGS
# ============================================================================


class VehicleSettings(BaseSettings):
    """Vehicle plugin directory configuration."""

    model_config = SettingsConfigDict(env_prefix="VEHICLE_")

    plugins_dir: str = "./vehicles"
    registry_file: str = "_registry.json"
    default_vehicle: str = "generic_obd2"
    max_vehicles: int = 20


# ============================================================================
# SCENARIO SETTINGS
# ============================================================================


class ScenarioSettings(BaseSettings):
    """Scenario engine configuration."""

    model_config = SettingsConfigDict(env_prefix="SCENARIO_")

    definitions_dir: str = "./scenarios"
    max_concurrent: int = 1  # Only one scenario at a time
    tick_interval_ms: int = 50  # Scenario update rate
    allow_override: bool = True  # Allow scenario to override live data


# ============================================================================
# REPLAY SETTINGS
# ============================================================================


class ReplaySettings(BaseSettings):
    """CAN log replay configuration."""

    model_config = SettingsConfigDict(env_prefix="REPLAY_")

    logs_dir: str = "./can_logs"
    max_speed: float = 10.0  # Maximum playback speed multiplier
    buffer_size: int = 5000  # Frames to preload
    auto_save: bool = True  # Auto-save CAN logs during live session
    save_interval_s: int = 30


# ============================================================================
# SECURITY SETTINGS (Phase 2+)
# ============================================================================


class SecuritySettings(BaseSettings):
    """Security configuration (prepared for Phase 2)."""

    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    enabled: bool = False  # Disabled in Phase 1
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    rate_limit_per_minute: int = 100


# ============================================================================
# MASTER SETTINGS (Aggregates all sub-settings)
# ============================================================================


class Settings(BaseSettings):
    """
    Master settings class aggregating all configuration groups.

    Usage:
        settings = get_settings()
        settings.server.port
        settings.serial.baud_rate
        settings.database.url
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    serial: SerialSettings = Field(default_factory=SerialSettings)
    can: CANSettings = Field(default_factory=CANSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    websocket: WebSocketSettings = Field(default_factory=WebSocketSettings)
    broadcast: BroadcastSettings = Field(default_factory=BroadcastSettings)
    diagnostics: DiagnosticsSettings = Field(default_factory=DiagnosticsSettings)
    vehicle: VehicleSettings = Field(default_factory=VehicleSettings)
    scenario: ScenarioSettings = Field(default_factory=ScenarioSettings)
    replay: ReplaySettings = Field(default_factory=ReplaySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)

    # --- Computed Properties ---

    @property
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent

    @property
    def vehicles_path(self) -> Path:
        """Get absolute path to vehicle plugins directory."""
        return self.project_root / self.vehicle.plugins_dir

    @property
    def scenarios_path(self) -> Path:
        """Get absolute path to scenarios directory."""
        return self.project_root / self.scenario.definitions_dir

    @property
    def replay_logs_path(self) -> Path:
        """Get absolute path to CAN log recordings."""
        return self.project_root / self.replay.logs_dir

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        self.vehicles_path.mkdir(parents=True, exist_ok=True)
        self.scenarios_path.mkdir(parents=True, exist_ok=True)
        self.replay_logs_path.mkdir(parents=True, exist_ok=True)


# ============================================================================
# SETTINGS SINGLETON
# ============================================================================


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached Settings instance (singleton).

    Uses lru_cache to ensure settings are loaded only once.
    Thread-safe due to GIL.

    Returns:
        Settings instance with all configuration loaded.
    """
    settings = Settings()
    settings.ensure_directories()
    return settings