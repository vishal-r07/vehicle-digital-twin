"""
============================================================================
AutoTwin AI - Vehicle Endpoints
============================================================================
Vehicle selection, listing, and plugin management.

Endpoints:
  GET    /api/vehicles              - List all vehicles
  GET    /api/vehicles/{slug}       - Get vehicle details
  POST   /api/vehicles/{slug}/select - Select active vehicle
  GET    /api/vehicles/{slug}/signals - Get CAN signals for vehicle
  GET    /api/vehicles/{slug}/subsystems - Get subsystem definitions
  GET    /api/vehicles/active       - Get currently selected vehicle
============================================================================
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.exceptions import VehicleNotFoundError

router = APIRouter()


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================


class VehicleSummary(BaseModel):
    id: str
    slug: str
    name: str
    make: str
    model: str
    year: Optional[int] = None
    category: Optional[str] = None
    is_active: bool = False


class VehicleDetail(BaseModel):
    slug: str
    name: str
    make: str
    model: str
    year: Optional[int] = None
    category: Optional[str] = None
    engine_type: Optional[str] = None
    transmission_type: Optional[str] = None
    signal_count: int = 0
    fault_rule_count: int = 0
    has_3d_model: bool = False
    dashboard_layout: Optional[Dict] = None


class VehicleListResponse(BaseModel):
    success: bool = True
    data: Dict[str, Any]
    meta: Dict[str, Any] = {}


class SelectVehicleRequest(BaseModel):
    load_dbc: bool = True
    load_rules: bool = True
    load_3d_model: bool = True


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("", response_model=VehicleListResponse)
async def list_vehicles(request: Request):
    """
    List all available vehicle plugins.

    Returns a list of all registered vehicles with basic metadata.
    """
    vehicle_service = request.app.state.vehicle_service
    vehicles = vehicle_service.list_all()

    return VehicleListResponse(
        success=True,
        data={
            "vehicles": vehicles,
            "count": len(vehicles),
            "active_vehicle": vehicle_service.get_active_slug(),
        },
    )


@router.get("/active")
async def get_active_vehicle(request: Request):
    """
    Get the currently selected/active vehicle.

    Returns null if no vehicle is selected.
    """
    vehicle_service = request.app.state.vehicle_service
    active = vehicle_service.get_active_vehicle()

    if not active:
        return {
            "success": True,
            "data": {"vehicle": None, "message": "No vehicle selected"},
        }

    return {
        "success": True,
        "data": {"vehicle": active},
    }


@router.get("/{slug}")
async def get_vehicle(slug: str, request: Request):
    """
    Get detailed information about a specific vehicle.

    Args:
        slug: Vehicle slug identifier (e.g., 'toyota_corolla_2020')
    """
    vehicle_service = request.app.state.vehicle_service
    vehicle = vehicle_service.get_vehicle(slug)

    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "VEHICLE_NOT_FOUND",
                "message": f"Vehicle '{slug}' not found",
                "details": {"slug": slug},
            },
        )

    return {
        "success": True,
        "data": {"vehicle": vehicle},
    }


@router.post("/{slug}/select")
async def select_vehicle(
    slug: str,
    body: SelectVehicleRequest = SelectVehicleRequest(),
    request: Request = None,
):
    """
    Select a vehicle as the active digital twin.

    This loads the vehicle's DBC, fault rules, and 3D model.
    Only one vehicle can be active at a time.

    Args:
        slug: Vehicle slug to select
        body: Options for what to load
    """
    vehicle_service = request.app.state.vehicle_service
    state_manager = request.app.state.state_manager
    can_parser = request.app.state.can_parser
    fault_engine = request.app.state.fault_engine
    event_bus = request.app.state.event_bus

    # Validate vehicle exists
    vehicle = vehicle_service.get_vehicle(slug)
    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "VEHICLE_NOT_FOUND",
                "message": f"Vehicle '{slug}' not found",
            },
        )

    # Select vehicle
    result = vehicle_service.select_vehicle(slug)

    # Load DBC and configure parser
    if body.load_dbc and result.get("dbc_path"):
        from app.can.dbc_loader import DBCParser
        dbc_parser = DBCParser(result["dbc_path"])
        dbc = dbc_parser.load()

        # Update CAN parser with vehicle-specific signals
        # (In production, convert DBC signals to SignalConfig)

    # Load fault rules
    if body.load_rules and result.get("fault_rules_path"):
        from app.diagnostics.fault_rules import RuleLoader
        rule_loader = RuleLoader(result["fault_rules_path"])
        rules = rule_loader.load()
        fault_engine.load_rules(rules)

    # Reset vehicle state
    await state_manager.reset()

    # Emit vehicle selected event
    from app.core.constants import EventType
    await event_bus.publish(
        EventType.VEHICLE_SELECTED,
        data={"slug": slug, "name": result.get("name", slug)},
        source="api",
    )

    return {
        "success": True,
        "data": {
            "vehicle": result,
            "message": f"Vehicle '{result.get('name', slug)}' selected",
        },
    }


@router.get("/{slug}/signals")
async def get_vehicle_signals(slug: str, request: Request):
    """
    Get all CAN signal definitions for a vehicle.

    Returns signal names, CAN IDs, units, ranges, and frequencies.
    """
    vehicle_service = request.app.state.vehicle_service
    signals = vehicle_service.get_vehicle_signals(slug)

    if signals is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "VEHICLE_NOT_FOUND", "message": f"Vehicle '{slug}' not found"},
        )

    return {
        "success": True,
        "data": {
            "vehicle": slug,
            "signals": signals,
            "count": len(signals) if signals else 0,
        },
    }


@router.get("/{slug}/subsystems")
async def get_vehicle_subsystems(slug: str, request: Request):
    """
    Get subsystem definitions and 3D positions for a vehicle.

    Used by the frontend to render clickable subsystem hotspots.
    """
    vehicle_service = request.app.state.vehicle_service
    subsystems = vehicle_service.get_vehicle_subsystems(slug)

    if subsystems is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "VEHICLE_NOT_FOUND", "message": f"Vehicle '{slug}' not found"},
        )

    return {
        "success": True,
        "data": {
            "vehicle": slug,
            "subsystems": subsystems,
        },
    }