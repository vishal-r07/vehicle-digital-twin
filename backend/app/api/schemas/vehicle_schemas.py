"""
============================================================================
AutoTwin AI - Vehicle API Schemas
============================================================================
Pydantic models for vehicle-related API endpoints.

Schemas:
  - VehicleSummarySchema:    Brief vehicle info for listing
  - VehicleDetailSchema:     Full vehicle profile
  - VehicleSelectRequest:    Request body for vehicle selection
  - VehicleSelectResponse:   Response after selection
  - VehicleListResponse:     List of all vehicles
  - VehicleSignalsResponse:  CAN signal definitions
  - SubsystemInfoSchema:     Subsystem 3D position and metadata
============================================================================
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# VEHICLE SUMMARY (List View)
# ============================================================================


class VehicleSummarySchema(BaseModel):
    """Brief vehicle information for listing displays."""

    id: str = Field(..., description="Unique vehicle identifier")
    slug: str = Field(..., description="URL-friendly identifier")
    name: str = Field(..., description="Display name")
    make: str = Field(..., description="Manufacturer")
    model: str = Field(..., description="Model name")
    year: Optional[int] = Field(None, description="Model year")
    category: Optional[str] = Field(None, description="sedan, SUV, EV, truck")
    is_active: bool = Field(False, description="Currently selected vehicle")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "1",
                    "slug": "toyota_corolla_2020",
                    "name": "Toyota Corolla 2020",
                    "make": "Toyota",
                    "model": "Corolla",
                    "year": 2020,
                    "category": "sedan",
                    "is_active": True,
                }
            ]
        }
    }


# ============================================================================
# VEHICLE DETAIL (Full Profile)
# ============================================================================


class VehicleDetailSchema(BaseModel):
    """Complete vehicle profile with all metadata."""

    slug: str
    name: str
    make: str
    model: str
    year: Optional[int] = None
    category: Optional[str] = None

    # Technical specifications
    engine_type: Optional[str] = Field(None, description="e.g., 2.0L I4")
    transmission_type: Optional[str] = Field(None, description="e.g., CVT, AT, MT")
    fuel_type: Optional[str] = Field(None, description="gasoline, diesel, electric, hybrid")
    drivetrain: Optional[str] = Field(None, description="FWD, RWD, AWD")

    # Dimensions (mm)
    length_mm: Optional[int] = None
    width_mm: Optional[int] = None
    height_mm: Optional[int] = None
    wheelbase_mm: Optional[int] = None

    # Plugin paths
    dbc_path: Optional[str] = Field(None, description="Path to DBC file")
    fault_rules_path: Optional[str] = Field(None, description="Path to fault rules YAML")
    model_3d_path: Optional[str] = Field(None, description="Path to 3D model (GLB)")
    dashboard_layout: Optional[Dict[str, Any]] = Field(None, description="Custom gauge layout")

    # Counts
    signal_count: int = Field(0, description="Number of CAN signals")
    fault_rule_count: int = Field(0, description="Number of fault rules")

    # Status
    is_active: bool = False
    has_3d_model: bool = False
    created_at: Optional[datetime] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "slug": "toyota_corolla_2020",
                    "name": "Toyota Corolla 2020",
                    "make": "Toyota",
                    "model": "Corolla",
                    "year": 2020,
                    "category": "sedan",
                    "engine_type": "2.0L I4",
                    "transmission_type": "CVT",
                    "fuel_type": "gasoline",
                    "signal_count": 16,
                    "fault_rule_count": 12,
                    "is_active": True,
                    "has_3d_model": True,
                }
            ]
        }
    }


# ============================================================================
# VEHICLE SELECTION
# ============================================================================


class VehicleSelectRequest(BaseModel):
    """Request body for selecting a vehicle."""

    load_dbc: bool = Field(True, description="Load DBC signal definitions")
    load_fault_rules: bool = Field(True, description="Load fault detection rules")
    load_3d_model: bool = Field(True, description="Load 3D model reference")
    reset_state: bool = Field(True, description="Reset vehicle state on selection")


class VehicleSelectResponse(BaseModel):
    """Response after vehicle selection."""

    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)
    message: str = ""

    class Data(BaseModel):
        vehicle: VehicleDetailSchema
        ws_channel: str = Field("default", description="WebSocket channel for this vehicle")
        signals_loaded: int = 0
        rules_loaded: int = 0


# ============================================================================
# VEHICLE LIST RESPONSE
# ============================================================================


class VehicleListResponse(BaseModel):
    """Response for listing all vehicles."""

    success: bool = True
    data: "VehicleListData"
    meta: Dict[str, Any] = Field(default_factory=dict)


class VehicleListData(BaseModel):
    vehicles: List[VehicleSummarySchema] = Field(default_factory=list)
    count: int = 0
    active_vehicle: Optional[str] = Field(None, description="Slug of active vehicle")


# ============================================================================
# VEHICLE SIGNALS
# ============================================================================


class SignalDefinitionSchema(BaseModel):
    """CAN signal definition for API response."""

    name: str
    display_name: str = ""
    can_id: int = Field(..., description="CAN arbitration ID")
    start_bit: int = 0
    bit_length: int = 8
    byte_order: str = "little_endian"
    is_signed: bool = False
    factor: float = 1.0
    offset: float = 0.0
    min_value: float = 0.0
    max_value: float = 1000.0
    unit: str = ""
    expected_frequency_hz: float = 20.0
    subsystem: str = ""


class VehicleSignalsResponse(BaseModel):
    """Response for vehicle signal definitions."""

    success: bool = True
    data: "VehicleSignalsData"


class VehicleSignalsData(BaseModel):
    vehicle: str
    signals: List[SignalDefinitionSchema] = Field(default_factory=list)
    count: int = 0


# ============================================================================
# SUBSYSTEM INFO
# ============================================================================


class SubsystemInfoSchema(BaseModel):
    """Subsystem definition with 3D position for digital twin."""

    name: str = Field(..., description="Subsystem identifier")
    display_name: str = Field(..., description="Human-readable name")
    position: List[float] = Field(
        default=[0, 0, 0],
        description="3D position [x, y, z]",
        min_length=3,
        max_length=3,
    )
    size: List[float] = Field(
        default=[1, 1, 1],
        description="3D bounding box size [w, h, d]",
        min_length=3,
        max_length=3,
    )
    color: str = Field("#00d4ff", description="Highlight color (hex)")
    signals: List[str] = Field(default_factory=list, description="Associated signals")
    description: str = ""

    @field_validator("position", "size")
    @classmethod
    def validate_vector(cls, v):
        if len(v) != 3:
            raise ValueError("Must be a 3-element vector [x, y, z]")
        return v


class VehicleSubsystemsResponse(BaseModel):
    """Response for vehicle subsystem definitions."""

    success: bool = True
    data: "VehicleSubsystemsData"


class VehicleSubsystemsData(BaseModel):
    vehicle: str
    subsystems: List[SubsystemInfoSchema] = Field(default_factory=list)
    count: int = 0


# ============================================================================
# GENERIC RESPONSE ENVELOPE
# ============================================================================


class APIResponseMeta(BaseModel):
    """Response metadata."""

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    request_id: str = ""
    duration_ms: float = 0.0


class APIErrorDetail(BaseModel):
    """Error detail structure."""

    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class APIErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: APIErrorDetail
    meta: APIResponseMeta = Field(default_factory=APIResponseMeta)


# Update forward references
VehicleListResponse.model_rebuild()
VehicleSignalsResponse.model_rebuild()
VehicleSubsystemsResponse.model_rebuild()