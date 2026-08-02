"""
vehicle_data.py - Vehicle data model

Design: Pydantic-like dataclass for type safety.
Future: Extend with validation, database ORM mapping, ML feature extraction.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional
import json


@dataclass
class VehicleData:
    """Complete vehicle state as received from STM32."""
    speed: float = 0.0           # km/h
    rpm: int = 0                 # revolutions per minute
    fuel: float = 100.0          # percentage
    temp: int = 25               # degrees Celsius
    battery: float = 12.6        # volts
    steering: float = 0.0        # degrees (-720 to 720)
    brake: int = 0               # 0 or 1
    accelerator: float = 0.0     # percentage
    gear: str = "P"              # P, R, N, D, S, L, M
    door: str = "Closed"         # Closed, FL, FR, etc.
    
    # Metadata
    timestamp: str = ""          # ISO 8601 timestamp
    sequence: int = 0            # Frame sequence number
    is_valid: bool = True        # Data integrity flag
    
    def to_json(self) -> str:
        """Serialize to JSON string for WebSocket broadcast."""
        data = asdict(self)
        if not self.timestamp:
            data['timestamp'] = datetime.now(timezone.utc).isoformat()
        return json.dumps(data)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        if not self.timestamp:
            data['timestamp'] = datetime.now(timezone.utc).isoformat()
        return data
    
    @classmethod
    def from_parsed(cls, parsed: dict, sequence: int = 0) -> 'VehicleData':
        """Create VehicleData from parsed serial output."""
        return cls(
            speed=float(parsed.get('Speed', 0)),
            rpm=int(float(parsed.get('RPM', 0))),
            fuel=float(parsed.get('Fuel', 100)),
            temp=int(float(parsed.get('Temp', 25))),
            battery=float(parsed.get('Battery', 12.6)),
            steering=float(parsed.get('Steering', 0)),
            brake=int(float(parsed.get('Brake', 0))),
            accelerator=float(parsed.get('Accel', 0)),
            gear=str(parsed.get('Gear', 'P')),
            door=str(parsed.get('Door', 'Closed')),
            timestamp=datetime.now(timezone.utc).isoformat(),
            sequence=sequence,
            is_valid=True
        )