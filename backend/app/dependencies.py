"""
============================================================================
AutoTwin AI - Dependency Injection Container
============================================================================
FastAPI dependency providers for all services and resources.

Dependencies are injected via FastAPI's Depends() mechanism, ensuring:
  - Single responsibility per endpoint
  - Easy testing (mock dependencies)
  - Automatic resource lifecycle management
  - Thread-safe singleton access

Usage in endpoints:
    from app.dependencies import get_state_manager, get_fault_engine

    @router.get("/state")
    async def get_state(
        state_mgr: VehicleStateManager = Depends(get_state_manager),
        fault_eng: FaultEngine = Depends(get_fault_engine),
    ):
        return state_mgr.get_current_state()
============================================================================
"""

from typing import AsyncGenerator, Generator

from fastapi import Depends, Request, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings


# ============================================================================
# SETTINGS DEPENDENCY
# ============================================================================


def get_app_settings() -> Settings:
    """Provide application settings (cached singleton)."""
    return get_settings()


# ============================================================================
# DATABASE DEPENDENCIES
# ============================================================================


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async database session.

    Yields a session and ensures it's closed after the request.
    Usage: session: AsyncSession = Depends(get_db_session)
    """
    from app.db.database import get_async_session_factory

    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================================
# CORE SERVICE DEPENDENCIES
# ============================================================================


def get_event_bus(request: Request):
    """Provide the application event bus."""
    return request.app.state.event_bus


def get_state_manager(request: Request):
    """Provide the Vehicle State Manager."""
    return request.app.state.state_manager


def get_can_parser(request: Request):
    """Provide the CAN Frame Parser."""
    return request.app.state.can_parser


def get_fault_engine(request: Request):
    """Provide the Fault Detection Engine."""
    return request.app.state.fault_engine


def get_health_calculator(request: Request):
    """Provide the Health Score Calculator."""
    return request.app.state.health_calculator


def get_serial_reader(request: Request):
    """Provide the Serial Reader (STM32 communication)."""
    return request.app.state.serial_reader


def get_broadcast_service(request: Request):
    """Provide the WebSocket Broadcast Service."""
    return request.app.state.broadcast_service


def get_ws_manager(request: Request):
    """Provide the WebSocket Connection Manager."""
    return request.app.state.ws_manager


def get_vehicle_service(request: Request):
    """Provide the Vehicle Plugin Service."""
    return request.app.state.vehicle_service


# ============================================================================
# SERVICE DEPENDENCIES (Business Logic Layer)
# ============================================================================


def get_diagnostic_service(request: Request):
    """Provide the Diagnostic Service (faults + health + timeline)."""
    from app.services.diagnostic_service import DiagnosticService

    return DiagnosticService(
        fault_engine=request.app.state.fault_engine,
        health_calculator=request.app.state.health_calculator,
        state_manager=request.app.state.state_manager,
        event_bus=request.app.state.event_bus,
    )


def get_scenario_service(request: Request):
    """Provide the Scenario Engine Service."""
    from app.services.scenario_service import ScenarioService

    return ScenarioService(
        state_manager=request.app.state.state_manager,
        event_bus=request.app.state.event_bus,
        settings=get_settings().scenario,
    )


# ============================================================================
# VEHICLE STATE DEPENDENCIES
# ============================================================================


def get_current_vehicle_state(request: Request):
    """
    Provide the current vehicle state snapshot.

    Returns a dictionary representation of the current state.
    """
    state_manager = request.app.state.state_manager
    return state_manager.get_state_dict()


def get_active_vehicle(request: Request):
    """Provide the currently selected vehicle profile."""
    vehicle_service = request.app.state.vehicle_service
    return vehicle_service.get_active_vehicle()


# ============================================================================
# QUERY PARAMETER DEPENDENCIES
# ============================================================================


def get_pagination_params(
    page: int = 1,
    size: int = 50,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    """
    Provide pagination parameters for list endpoints.

    Query params: ?page=1&size=50&sort_by=created_at&sort_order=desc
    """
    # Clamp values
    page = max(1, page)
    size = max(1, min(size, 200))  # Max 200 items per page

    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    return {
        "page": page,
        "size": size,
        "offset": (page - 1) * size,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }


def get_time_range_params(
    start: str = None,
    end: str = None,
    hours: int = 24,
):
    """
    Provide time range parameters for history queries.

    Query params: ?start=2026-01-15T00:00:00&end=2026-01-15T23:59:59
    Or: ?hours=24 (last 24 hours)
    """
    from datetime import datetime, timedelta, timezone

    if start and end:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
    else:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(hours=hours)

    return {
        "start": start_dt,
        "end": end_dt,
    }


def get_severity_filter(severity: str = None):
    """
    Provide severity filter for fault queries.

    Query params: ?severity=HIGH
    Valid values: INFO, LOW, MEDIUM, HIGH, CRITICAL
    """
    valid_severities = {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL", None}
    if severity and severity.upper() not in valid_severities:
        severity = None
    return severity.upper() if severity else None


# ============================================================================
# WEBSOCKET DEPENDENCIES
# ============================================================================


async def get_ws_client_id(websocket: WebSocket) -> str:
    """Generate a unique client ID for WebSocket connections."""
    import uuid
    return str(uuid.uuid4())[:8]


# ============================================================================
# COMPOSITE DEPENDENCIES (Multiple services)
# ============================================================================


class ServiceContainer:
    """
    Container providing access to all services.
    Useful for endpoints that need multiple services.
    """

    def __init__(self, request: Request):
        self.settings = get_settings()
        self.event_bus = request.app.state.event_bus
        self.state_manager = request.app.state.state_manager
        self.can_parser = request.app.state.can_parser
        self.fault_engine = request.app.state.fault_engine
        self.health_calculator = request.app.state.health_calculator
        self.serial_reader = request.app.state.serial_reader
        self.broadcast_service = request.app.state.broadcast_service
        self.ws_manager = request.app.state.ws_manager
        self.vehicle_service = request.app.state.vehicle_service


def get_service_container(request: Request) -> ServiceContainer:
    """Provide a container with all services."""
    return ServiceContainer(request)


# ============================================================================
# DEPENDENCY TYPE ALIASES (for cleaner endpoint signatures)
# ============================================================================

# Usage in endpoints:
#   async def my_endpoint(
#       state: VehicleStateManager = Depends(get_state_manager),
#       faults: FaultEngine = Depends(get_fault_engine),
#       session: AsyncSession = Depends(get_db_session),
#   ):
#       ...

SettingsDep = Depends(get_app_settings)
StateDep = Depends(get_state_manager)
FaultDep = Depends(get_fault_engine)
HealthDep = Depends(get_health_calculator)
SerialDep = Depends(get_serial_reader)
BroadcastDep = Depends(get_broadcast_service)
WSManagerDep = Depends(get_ws_manager)
VehicleDep = Depends(get_vehicle_service)
DiagnosticDep = Depends(get_diagnostic_service)
ScenarioDep = Depends(get_scenario_service)
DBSessionDep = Depends(get_db_session)
PaginationDep = Depends(get_pagination_params)