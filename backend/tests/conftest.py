"""
============================================================================
AutoTwin AI - Test Fixtures & Configuration
============================================================================
Shared pytest fixtures for all test modules.

Fixtures:
  - event_bus:         Fresh EventBus per test
  - state_manager:     VehicleStateManager with event bus
  - can_parser:        CANFrameParser with Phase 1 signals
  - fault_engine:      FaultEngine with default rules
  - health_calculator: HealthCalculator instance
  - vehicle_state:     Fresh VehicleState object
  - sample_signals:    Dictionary of realistic signal values
  - serial_frame:      Simulated serial frame data
============================================================================
"""

import asyncio
import time
from typing import Any, Dict

import pytest
import pytest_asyncio

from app.core.event_bus import EventBus
from app.core.state_manager import VehicleStateManager
from app.can.frame_parser import CANFrameParser
from app.can.signal_definitions import Phase1Signals
from app.diagnostics.fault_engine import FaultEngine
from app.diagnostics.fault_rules import RuleLoader
from app.vehicle.vehicle_state import VehicleState
from app.vehicle.state_updater import StateUpdater
from app.vehicle.health_calculator import HealthCalculator
from app.scenarios.scenario_definitions import ScenarioLibrary


# ============================================================================
# EVENT LOOP FIXTURE
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# CORE FIXTURES
# ============================================================================


@pytest.fixture
def event_bus():
    """Fresh EventBus for each test."""
    bus = EventBus(history_size=100)
    yield bus
    # Cleanup: don't await in sync fixture


@pytest_asyncio.fixture
async def async_event_bus():
    """Async EventBus with proper cleanup."""
    bus = EventBus(history_size=100)
    yield bus
    await bus.shutdown()


@pytest.fixture
def state_manager(event_bus):
    """VehicleStateManager with event bus."""
    return VehicleStateManager(event_bus, history_size=50)


@pytest.fixture
def can_parser():
    """CANFrameParser with Phase 1 signal definitions."""
    return CANFrameParser()


@pytest.fixture
def fault_engine(event_bus):
    """FaultEngine with default rules loaded."""
    engine = FaultEngine(event_bus)
    loader = RuleLoader()
    rules = loader.load()
    engine.load_rules(rules)
    return engine


@pytest.fixture
def health_calculator(event_bus):
    """HealthCalculator instance."""
    return HealthCalculator(event_bus)


@pytest.fixture
def vehicle_state():
    """Fresh VehicleState object."""
    return VehicleState()


@pytest.fixture
def state_updater():
    """StateUpdater instance."""
    return StateUpdater()


@pytest.fixture
def scenario_library():
    """ScenarioLibrary with built-in scenarios."""
    return ScenarioLibrary()


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================


@pytest.fixture
def sample_signals() -> Dict[str, Any]:
    """Realistic vehicle signal values for testing."""
    return {
        "speed": 58.0,
        "rpm": 2450,
        "fuel": 82.0,
        "temp": 91,
        "battery": 12.5,
        "steering": -12.0,
        "brake": 0,
        "accelerator": 35.0,
        "gear": "D",
        "door": "Closed",
        "indicator": 0,
        "headlight": 1,
        "engine_load": 45.0,
        "ambient_temp": 22,
        "odometer": 45230.5,
    }


@pytest.fixture
def overheat_signals() -> Dict[str, Any]:
    """Signals simulating engine overheat condition."""
    return {
        "speed": 60.0,
        "rpm": 3000,
        "fuel": 75.0,
        "temp": 112,  # Above 105 threshold
        "battery": 12.5,
        "steering": 0.0,
        "brake": 0,
        "accelerator": 40.0,
        "gear": "D",
        "door": "Closed",
        "engine_load": 70.0,
    }


@pytest.fixture
def low_battery_signals() -> Dict[str, Any]:
    """Signals simulating low battery condition."""
    return {
        "speed": 40.0,
        "rpm": 1800,
        "fuel": 60.0,
        "temp": 88,
        "battery": 11.2,  # Below 11.5 threshold
        "steering": 5.0,
        "brake": 0,
        "accelerator": 20.0,
        "gear": "D",
        "door": "Closed",
    }


@pytest.fixture
def critical_signals() -> Dict[str, Any]:
    """Signals simulating multiple critical conditions."""
    return {
        "speed": 20.0,
        "rpm": 1000,
        "fuel": 3.0,  # Critical fuel
        "temp": 125,  # Critical overheat
        "battery": 10.2,  # Critical battery
        "steering": 0.0,
        "brake": 1,
        "accelerator": 0.0,
        "gear": "N",
        "door": "FL",
    }


@pytest.fixture
def serial_frame_data() -> Dict[str, str]:
    """Raw serial frame as received from STM32 (string values)."""
    return {
        "Speed": "58.00",
        "RPM": "2450",
        "Fuel": "82.0",
        "Temp": "91",
        "Battery": "12.50",
        "Steering": "-12.0",
        "Brake": "0",
        "Accel": "35.0",
        "Gear": "D",
        "Door": "Closed",
        "Indicator": "0",
        "Headlight": "1",
        "EngineLoad": "45.0",
        "AmbientTemp": "22",
        "Odometer": "45230.5",
        "WheelFL": "57.80",
        "WheelFR": "58.10",
        "WheelRL": "57.90",
        "WheelRR": "58.00",
        "BrakePressure": "0.0",
        "ABS": "0",
        "FrameCount": "1542",
        "CANActive": "1",
        "Uptime": "3600",
        "Seq": "1542",
    }


@pytest.fixture
def raw_can_speed_frame() -> bytes:
    """Raw CAN frame for speed signal (0x100).
    Speed = 58.00 km/h → raw = 5800 = 0x16A8 (little-endian)
    """
    return bytes([0xA8, 0x16, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])


@pytest.fixture
def raw_can_rpm_frame() -> bytes:
    """Raw CAN frame for RPM signal (0x101).
    RPM = 2450 → 0x0992 (little-endian)
    """
    return bytes([0x92, 0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])


@pytest.fixture
def raw_can_temp_frame() -> bytes:
    """Raw CAN frame for temperature signal (0x103).
    Temp = 91°C → raw = 91 + 40 = 131 = 0x83
    """
    return bytes([0x83, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


@pytest.fixture
def wait_for_event():
    """Helper to wait for an event with timeout."""
    async def _wait(bus: EventBus, event_type: str, timeout: float = 1.0):
        received = []

        async def handler(event):
            received.append(event)

        sub = bus.subscribe(event_type, handler)
        await asyncio.sleep(timeout)
        bus.unsubscribe(sub)
        return received

    return _wait