"""
data_parser.py - Parse and validate vehicle data from serial frames

Responsibilities:
- Validate data types and ranges
- Convert string values to proper types
- Apply engineering unit validation
- Flag anomalies

Future: Add statistical validation, ML-based anomaly detection.
"""

from typing import Optional, Tuple
from .config import config
from .models.vehicle_data import VehicleData
from .utils.logger import setup_logger

logger = setup_logger("DataParser")


class DataParser:
    """Validates and converts raw serial frame data into VehicleData objects."""
    
    def __init__(self):
        self._sequence: int = 0
        self._vehicle_config = config.vehicle
    
    def parse(self, raw_frame: dict) -> Optional[VehicleData]:
        """
        Parse a raw frame dictionary into a validated VehicleData object.
        
        Args:
            raw_frame: Dictionary of key-value pairs from serial
            
        Returns:
            VehicleData if valid, None if parsing fails
        """
        try:
            self._sequence += 1
            vehicle_data = VehicleData.from_parsed(raw_frame, self._sequence)
            
            # Validate ranges
            if not self._validate(vehicle_data):
                logger.warning(f"Frame {self._sequence} failed validation")
                vehicle_data.is_valid = False
            
            return vehicle_data
            
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Parse error: {e} | Raw: {raw_frame}")
            return None
    
    def _validate(self, data: VehicleData) -> bool:
        """Validate all signal ranges."""
        vc = self._vehicle_config
        
        checks = [
            0 <= data.speed <= vc.speed_max,
            0 <= data.rpm <= vc.rpm_max,
            0 <= data.fuel <= 100,
            -40 <= data.temp <= 215,
            0 <= data.battery <= 20,
            -vc.steering_max <= data.steering <= vc.steering_max,
            data.brake in (0, 1),
            0 <= data.accelerator <= 100,
            data.gear in ('P', 'R', 'N', 'D', 'S', 'L', 'M', '?'),
        ]
        
        return all(checks)
    
    def get_warnings(self, data: VehicleData) -> list:
        """Generate warning messages for threshold violations."""
        warnings = []
        vc = self._vehicle_config
        
        if data.temp >= vc.temp_critical_threshold:
            warnings.append(f"CRITICAL: Engine temp {data.temp}°C exceeds {vc.temp_critical_threshold}°C")
        elif data.temp >= vc.temp_high_threshold:
            warnings.append(f"WARNING: Engine temp {data.temp}°C approaching limit")
        
        if data.fuel <= vc.fuel_low_threshold:
            warnings.append(f"WARNING: Fuel level {data.fuel}% is low")
        
        if data.battery <= vc.battery_low_threshold:
            warnings.append(f"WARNING: Battery voltage {data.battery}V is low")
        
        if data.rpm >= vc.rpm_redline:
            warnings.append(f"WARNING: RPM {data.rpm} in redline zone")
        
        return warnings