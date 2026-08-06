"""
============================================================================
AutoTwin AI - Software CAN Simulator
============================================================================
Generates realistic vehicle data without any hardware.

Use cases:
  - Development and testing without STM32
  - Demo mode for presentations
  - Unit testing the full pipeline
  - Scenario validation

The simulator generates physically plausible signals:
  - Speed follows acceleration/braking dynamics
  - RPM correlates with speed and gear
  - Temperature rises with engine load
  - Fuel decreases over time
  - Steering oscillates smoothly

Usage:
    sim = CANSimulator(event_bus)
    await sim.connect()
    frame = await sim.read(timeout=0.05)
    # frame.signals contains {"speed": 58.0, "rpm": 2450, ...}
============================================================================
"""

import asyncio
import math
import random
import time
from typing import Any, Dict, Optional

from loguru import logger

from app.core.constants import EventType, GearPosition
from app.core.event_bus import EventBus
from app.hardware.base_interface import (
    HardwareMetadata,
    HardwareStatus,
    IHardwareSource,
    RawFrame,
    SourceType,
)


# ============================================================================
# SIMULATOR IMPLEMENTATION
# ============================================================================


class CANSimulator(IHardwareSource):
    """
    Software vehicle data simulator.

    Generates realistic driving data at configurable update rate.
    Simulates a complete driving cycle with varying conditions.
    """

    def __init__(self, event_bus: EventBus, update_rate_hz: float = 20.0):
        super().__init__()
        self._event_bus = event_bus
        self._update_interval = 1.0 / update_rate_hz

        # Simulation state
        self._sim_time: float = 0.0
        self._running: bool = False
        self._sequence: int = 0

        # Vehicle simulation state
        self._speed: float = 0.0
        self._rpm: float = 800.0
        self._fuel: float = 85.0
        self._temp: float = 65.0
        self._battery: float = 12.8
        self._steering: float = 0.0
        self._brake: bool = False
        self._accelerator: float = 0.0
        self._gear: str = "P"
        self._door: str = "Closed"
        self._indicator: int = 0
        self._headlight: int = 1
        self._engine_load: float = 0.0
        self._ambient_temp: float = 22
        self._odometer: float = 45230.5
        self._wheel_speeds: Dict[str, float] = {"fl": 0, "fr": 0, "rl": 0, "rr": 0}

        # Simulation mode
        self._mode: str = "normal_driving"
        self._mode_start_time: float = 0.0

        # Random seed for reproducibility (optional)
        self._rng = random.Random(42)

    # ========================================================================
    # IHardwareSource INTERFACE
    # ========================================================================

    @property
    def source_type(self) -> SourceType:
        return SourceType.SIMULATOR

    @property
    def is_connected(self) -> bool:
        return self._status == HardwareStatus.CONNECTED and self._running

    async def connect(self) -> bool:
        """Start the simulator."""
        self._running = True
        self._sim_time = 0.0
        self._mode_start_time = 0.0
        self._mark_connected()

        logger.info(f"CANSimulator: started (mode={self._mode}, rate={1.0/self._update_interval:.0f}Hz)")
        return True

    async def disconnect(self) -> None:
        """Stop the simulator."""
        self._running = False
        self._mark_disconnected()
        logger.info("CANSimulator: stopped")

    async def read(self, timeout: float = 0.1) -> Optional[RawFrame]:
        """Generate and return the next simulated frame."""
        if not self._running:
            return None

        # Simulate timing
        await asyncio.sleep(min(timeout, self._update_interval))

        # Advance simulation
        self._sim_time += self._update_interval
        self._sequence += 1

        # Update simulation state
        self._update_simulation()

        # Build frame
        frame = RawFrame(
            signals=self._get_signals_dict(),
            source_type="simulator",
            received_at=time.time(),
            sequence=self._sequence,
        )

        self._record_frame()
        return frame

    def get_metadata(self) -> HardwareMetadata:
        return HardwareMetadata(
            source_type=SourceType.SIMULATOR,
            name="Software CAN Simulator",
            port="virtual",
            baud_rate=0,
            can_baud_rate=500000,
            firmware_version="sim-1.0",
            connected_since=self._connected_at,
            frames_received=self._frames_received,
            errors=self._errors,
            last_frame_time=self._last_frame_at,
        )

    # ========================================================================
    # SIMULATION MODES
    # ========================================================================

    def set_mode(self, mode: str) -> None:
        """Set simulation mode."""
        self._mode = mode
        self._mode_start_time = self._sim_time
        logger.info(f"CANSimulator: mode set to '{mode}'")

    # ========================================================================
    # SIMULATION ENGINE
    # ========================================================================

    def _update_simulation(self) -> None:
        """Advance the vehicle simulation by one timestep."""
        t = self._sim_time
        dt = self._update_interval

        if self._mode == "normal_driving":
            self._simulate_normal_driving(t, dt)
        elif self._mode == "city_traffic":
            self._simulate_city_traffic(t, dt)
        elif self._mode == "highway":
            self._simulate_highway(t, dt)
        elif self._mode == "engine_overheat":
            self._simulate_overheat(t, dt)
        elif self._mode == "battery_failure":
            self._simulate_battery_failure(t, dt)
        else:
            self._simulate_normal_driving(t, dt)

        # Common updates
        self._update_fuel(dt)
        self._update_odometer(dt)
        self._update_wheel_speeds()

    def _simulate_normal_driving(self, t: float, dt: float) -> None:
        """Normal driving with varying speed."""
        # Speed: smooth oscillation 30-90 km/h
        target_speed = 60 + 30 * math.sin(t * 0.1)
        self._speed += (target_speed - self._speed) * dt * 0.5
        self._speed = max(0, min(300, self._speed))

        # Accelerator
        if target_speed > self._speed:
            self._accelerator = min(100, (target_speed - self._speed) * 3)
            self._brake = False
        else:
            self._accelerator = 0
            self._brake = (self._speed - target_speed) > 5

        # RPM correlates with speed and gear
        self._update_gear()
        base_rpm = 800 + self._speed * 35
        self._rpm = base_rpm + self._rng.gauss(0, 50)
        self._rpm = max(700, min(8000, self._rpm))

        # Engine load
        self._engine_load = min(100, self._accelerator * 0.8 + self._speed * 0.1)

        # Temperature: rises to ~90°C
        target_temp = 88 + 5 * math.sin(t * 0.02)
        self._temp += (target_temp - self._temp) * dt * 0.1

        # Battery: stable around 13.8V when engine running
        self._battery = 13.8 + self._rng.gauss(0, 0.05)

        # Steering: gentle oscillation
        self._steering = 15 * math.sin(t * 0.3) + self._rng.gauss(0, 2)

        # Indicators: occasional turn signal
        if int(t) % 30 < 3:
            self._indicator = 1  # Left
        elif int(t) % 30 >= 15 and int(t) % 30 < 18:
            self._indicator = 2  # Right
        else:
            self._indicator = 0

        # Doors: closed
        self._door = "Closed"

    def _simulate_city_traffic(self, t: float, dt: float) -> None:
        """Stop-and-go city traffic."""
        cycle = t % 60  # 60-second cycle

        if cycle < 20:  # Stopped
            target_speed = 0
        elif cycle < 35:  # Accelerating
            target_speed = 40
        elif cycle < 50:  # Cruising
            target_speed = 35 + 10 * math.sin(t * 0.5)
        else:  # Braking
            target_speed = 0

        self._speed += (target_speed - self._speed) * dt * 2.0
        self._speed = max(0, self._speed)

        self._brake = target_speed < self._speed - 2
        self._accelerator = 0 if self._brake else min(60, (target_speed - self._speed) * 5)

        self._update_gear()
        self._rpm = 800 + self._speed * 40 + self._rng.gauss(0, 30)
        self._rpm = max(700, min(4000, self._rpm))
        self._engine_load = self._accelerator * 0.7

        target_temp = 92
        self._temp += (target_temp - self._temp) * dt * 0.05
        self._battery = 13.7 + self._rng.gauss(0, 0.1)
        self._steering = 45 * math.sin(t * 0.4) + self._rng.gauss(0, 5)

    def _simulate_highway(self, t: float, dt: float) -> None:
        """Highway cruising at high speed."""
        target_speed = 120 + 5 * math.sin(t * 0.05)
        self._speed += (target_speed - self._speed) * dt * 0.3
        self._accelerator = 25 + 5 * math.sin(t * 0.1)
        self._brake = False

        self._gear = "D"
        self._rpm = 2200 + self._speed * 8 + self._rng.gauss(0, 20)
        self._engine_load = 35 + 5 * math.sin(t * 0.1)

        self._temp = 90 + 2 * math.sin(t * 0.01)
        self._battery = 14.0 + self._rng.gauss(0, 0.03)
        self._steering = 3 * math.sin(t * 0.2) + self._rng.gauss(0, 1)

    def _simulate_overheat(self, t: float, dt: float) -> None:
        """Engine overheating scenario."""
        elapsed = t - self._mode_start_time

        self._speed = 60 + 10 * math.sin(t * 0.2)
        self._accelerator = 40
        self._rpm = 3000 + self._rng.gauss(0, 100)
        self._engine_load = 70

        # Temperature rises continuously
        if elapsed < 30:
            self._temp = 90 + elapsed * 1.0  # Rise to 120°C in 30s
        else:
            self._temp = 120 + math.sin(t * 2) * 2  # Stay critical

        self._battery = 13.5
        self._steering = 5 * math.sin(t * 0.3)

    def _simulate_battery_failure(self, t: float, dt: float) -> None:
        """Battery voltage dropping."""
        elapsed = t - self._mode_start_time

        self._speed = 50 + 10 * math.sin(t * 0.2)
        self._rpm = 2500 + self._rng.gauss(0, 50)
        self._accelerator = 30
        self._engine_load = 40

        # Battery drops from 12.6 to 9.0 over 60 seconds
        self._battery = max(9.0, 12.6 - elapsed * 0.06)
        self._temp = 88
        self._steering = 10 * math.sin(t * 0.3)

    # ========================================================================
    # HELPER SIMULATIONS
    # ========================================================================

    def _update_gear(self) -> None:
        """Determine gear based on speed."""
        if self._speed < 1:
            self._gear = "P"
        elif self._speed < 20:
            self._gear = "D"
        elif self._speed < 50:
            self._gear = "D"
        else:
            self._gear = "D"

    def _update_fuel(self, dt: float) -> None:
        """Decrease fuel based on engine load."""
        consumption_rate = 0.001 + self._engine_load * 0.00005
        self._fuel = max(0, self._fuel - consumption_rate * dt * 60)

    def _update_odometer(self, dt: float) -> None:
        """Update odometer based on speed."""
        self._odometer += (self._speed / 3600) * dt

    def _update_wheel_speeds(self) -> None:
        """Update individual wheel speeds (slight variation)."""
        base = self._speed
        self._wheel_speeds = {
            "fl": base + self._rng.gauss(0, 0.1),
            "fr": base + self._rng.gauss(0, 0.1),
            "rl": base + self._rng.gauss(0, 0.1),
            "rr": base + self._rng.gauss(0, 0.1),
        }

    def _get_signals_dict(self) -> Dict[str, Any]:
        """Build the signals dictionary matching serial protocol format."""
        return {
            "Speed": f"{self._speed:.2f}",
            "RPM": str(int(self._rpm)),
            "Fuel": f"{self._fuel:.1f}",
            "Temp": str(int(self._temp)),
            "Battery": f"{self._battery:.2f}",
            "Steering": f"{self._steering:.1f}",
            "Brake": "1" if self._brake else "0",
            "Accel": f"{self._accelerator:.1f}",
            "Gear": self._gear,
            "Door": self._door,
            "Indicator": str(self._indicator),
            "Headlight": str(self._headlight),
            "EngineLoad": f"{self._engine_load:.1f}",
            "AmbientTemp": str(self._ambient_temp),
            "Odometer": f"{self._odometer:.1f}",
            "WheelFL": f"{self._wheel_speeds['fl']:.2f}",
            "WheelFR": f"{self._wheel_speeds['fr']:.2f}",
            "WheelRL": f"{self._wheel_speeds['rl']:.2f}",
            "WheelRR": f"{self._wheel_speeds['rr']:.2f}",
            "BrakePressure": f"{50.0 if self._brake else 0.0:.1f}",
            "ABS": "0",
            "FrameCount": str(self._sequence),
            "CANActive": "1",
            "Uptime": str(int(self._sim_time)),
            "Seq": str(self._sequence),
        }

    # ========================================================================
    # STATISTICS
    # ========================================================================

    def get_stats(self) -> Dict[str, Any]:
        return {
            "mode": self._mode,
            "sim_time_s": self._sim_time,
            "frames_generated": self._frames_received,
            "speed": self._speed,
            "rpm": self._rpm,
            "fuel": self._fuel,
            "temp": self._temp,
            "battery": self._battery,
            "update_rate_hz": 1.0 / self._update_interval,
        }