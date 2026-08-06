"""
============================================================================
AutoTwin AI - Diagnostics Endpoints
============================================================================
Fault queries, management, and timeline access.

Endpoints:
  GET    /api/diagnostics/faults              - Get active faults
  GET    /api/diagnostics/faults/history      - Get fault history
  GET    /api/diagnostics/faults/{fault_id}   - Get fault details
  POST   /api/diagnostics/faults/{fault_id}/acknowledge - Acknowledge fault
  GET    /api/diagnostics/timeline            - Get event timeline
  GET    /api/diagnostics/rules               - List fault rules
  PUT    /api/diagnostics/rules/{rule_id}/toggle - Enable/disable rule
  GET    /api/diagnostics/recommendations     - Get repair recommendations
============================================================================
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter()


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("/faults")
async def get_active_faults(
    request: Request,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    subsystem: Optional[str] = Query(None, description="Filter by subsystem"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get all currently active (unresolved) faults.

    Query Parameters:
        severity: Filter by severity (INFO, LOW, MEDIUM, HIGH, CRITICAL)
        subsystem: Filter by subsystem name
        limit: Maximum number of results
    """
    fault_engine = request.app.state.fault_engine

    faults = fault_engine.get_active_faults()

    # Apply filters
    if severity:
        faults = [f for f in faults if f.severity == severity.upper()]
    if subsystem:
        faults = [f for f in faults if f.subsystem == subsystem]

    # Sort by priority (lower = more urgent)
    faults.sort(key=lambda f: f.priority)

    # Limit
    faults = faults[:limit]

    return {
        "success": True,
        "data": {
            "faults": [f.to_dict() for f in faults],
            "count": len(faults),
            "total_active": fault_engine.active_fault_count,
        },
    }


@router.get("/faults/history")
async def get_fault_history(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    severity: Optional[str] = None,
):
    """Get historical fault events (including resolved)."""
    fault_engine = request.app.state.fault_engine
    history = fault_engine.get_fault_history(limit=limit)

    if severity:
        history = [f for f in history if f.severity == severity.upper()]

    return {
        "success": True,
        "data": {
            "faults": [f.to_dict() for f in history],
            "count": len(history),
        },
    }


@router.get("/faults/{fault_id}")
async def get_fault_details(fault_id: str, request: Request):
    """
    Get detailed information about a specific fault.

    Includes recommendation and diagnostic context.
    """
    fault_engine = request.app.state.fault_engine

    # Search active faults
    for fault in fault_engine.get_active_faults():
        if fault.fault_id == fault_id:
            # Get recommendation
            from app.diagnostics.recommendations import RecommendationEngine
            rec_engine = RecommendationEngine()
            recommendation = rec_engine.get_recommendation(fault)

            return {
                "success": True,
                "data": {
                    "fault": fault.to_dict(),
                    "recommendation": recommendation.to_dict(),
                },
            }

    # Search history
    for fault in fault_engine.get_fault_history(limit=500):
        if fault.fault_id == fault_id:
            return {
                "success": True,
                "data": {"fault": fault.to_dict(), "recommendation": None},
            }

    raise HTTPException(
        status_code=404,
        detail={"code": "FAULT_NOT_FOUND", "message": f"Fault '{fault_id}' not found"},
    )


@router.post("/faults/{fault_id}/acknowledge")
async def acknowledge_fault(fault_id: str, request: Request):
    """
    Acknowledge a fault (marks as seen by technician).

    Does not resolve the fault — just indicates awareness.
    """
    fault_engine = request.app.state.fault_engine

    success = fault_engine.acknowledge_fault(fault_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail={"code": "FAULT_NOT_FOUND", "message": f"Fault '{fault_id}' not found"},
        )

    return {
        "success": True,
        "data": {"fault_id": fault_id, "acknowledged": True},
    }


@router.get("/timeline")
async def get_timeline(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
):
    """
    Get the diagnostic event timeline.

    Returns chronological list of all diagnostic events.
    """
    fault_engine = request.app.state.fault_engine
    timeline = fault_engine._timeline

    if event_type:
        entries = timeline.get_by_type(event_type, limit=limit)
    elif severity:
        entries = timeline.get_by_severity(severity, limit=limit)
    else:
        entries = timeline.get_recent(limit=limit)

    return {
        "success": True,
        "data": {
            "events": [e.to_dict() for e in entries],
            "count": len(entries),
            "total_entries": timeline.size,
        },
    }


@router.get("/rules")
async def get_fault_rules(request: Request):
    """List all fault detection rules with their status."""
    fault_engine = request.app.state.fault_engine

    rules = []
    for rule in fault_engine._rules:
        rules.append(rule.to_dict())

    return {
        "success": True,
        "data": {
            "rules": rules,
            "count": len(rules),
            "enabled_count": sum(1 for r in rules if r["enabled"]),
        },
    }


@router.put("/rules/{rule_id}/toggle")
async def toggle_rule(rule_id: str, request: Request):
    """Enable or disable a fault detection rule."""
    fault_engine = request.app.state.fault_engine

    # Find rule and toggle
    for rule in fault_engine._rules:
        if rule.rule_id == rule_id:
            rule.enabled = not rule.enabled
            return {
                "success": True,
                "data": {
                    "rule_id": rule_id,
                    "enabled": rule.enabled,
                    "message": f"Rule '{rule_id}' {'enabled' if rule.enabled else 'disabled'}",
                },
            }

    raise HTTPException(
        status_code=404,
        detail={"code": "RULE_NOT_FOUND", "message": f"Rule '{rule_id}' not found"},
    )


@router.get("/recommendations")
async def get_recommendations(request: Request):
    """Get repair recommendations for all active faults."""
    fault_engine = request.app.state.fault_engine
    from app.diagnostics.recommendations import RecommendationEngine

    rec_engine = RecommendationEngine()
    active_faults = fault_engine.get_active_faults()
    recommendations = rec_engine.get_recommendations_batch(active_faults)

    return {
        "success": True,
        "data": {
            "recommendations": [r.to_dict() for r in recommendations],
            "count": len(recommendations),
        },
    }