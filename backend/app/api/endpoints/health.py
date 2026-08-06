"""
============================================================================
AutoTwin AI - Health Score Endpoints
============================================================================
Vehicle health scores, trends, and history.

Endpoints:
  GET  /api/health/current    - Current health scores
  GET  /api/health/history    - Health score history
  GET  /api/health/trends     - Health trends per subsystem
  GET  /api/health/summary    - Quick health summary
============================================================================
"""

from typing import Optional

from fastapi import APIRouter, Query, Request

router = APIRouter()


@router.get("/current")
async def get_current_health(request: Request):
    """
    Get current health scores for all subsystems.

    Returns overall score and per-subsystem breakdown.
    """
    health_calculator = request.app.state.health_calculator
    state_manager = request.app.state.state_manager
    fault_engine = request.app.state.fault_engine

    # Get current state and faults
    state = state_manager.get_state_dict()
    active_faults = fault_engine.get_active_faults()

    # Calculate health
    fault_dicts = [
        {
            "subsystem": f.subsystem,
            "severity": f.severity,
            "confidence": f.confidence,
        }
        for f in active_faults
    ]

    from app.vehicle.vehicle_state import VehicleState
    from app.vehicle.health_calculator import HealthCalculator

    calculator = HealthCalculator()
    vehicle_state = VehicleState()
    scores = calculator.calculate(vehicle_state, fault_dicts)

    return {
        "success": True,
        "data": scores.to_dict(),
    }


@router.get("/history")
async def get_health_history(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    hours: int = Query(24, ge=1, le=168),
):
    """
    Get health score history over time.

    Query Parameters:
        limit: Maximum number of snapshots
        hours: Look-back window in hours
    """
    health_calculator = request.app.state.health_calculator
    history = health_calculator.get_history(limit=limit)

    return {
        "success": True,
        "data": {
            "snapshots": [s.to_dict() for s in history],
            "count": len(history),
        },
    }


@router.get("/trends")
async def get_health_trends(request: Request):
    """
    Get health trends for each subsystem.

    Shows whether each subsystem is improving, stable, or declining.
    """
    health_calculator = request.app.state.health_calculator

    subsystems = ["engine", "transmission", "brakes", "cooling", "battery", "electrical"]
    trends = {}

    for subsystem in subsystems:
        trends[subsystem] = health_calculator.get_trend(subsystem)

    return {
        "success": True,
        "data": {"trends": trends},
    }


@router.get("/summary")
async def get_health_summary(request: Request):
    """
    Get a quick health summary (single score + status).

    Optimized for status bar / header display.
    """
    state_manager = request.app.state.state_manager
    fault_engine = request.app.state.fault_engine

    state = state_manager.get_state_dict()
    active_faults = fault_engine.active_fault_count

    # Simplified health calculation
    overall = 100.0
    if active_faults > 0:
        overall -= active_faults * 5.0
    overall = max(0, min(100, overall))

    status = "good" if overall >= 80 else "warning" if overall >= 60 else "critical"

    return {
        "success": True,
        "data": {
            "overall_score": round(overall, 1),
            "status": status,
            "active_faults": active_faults,
            "can_active": state.get("can_active", False),
        },
    }