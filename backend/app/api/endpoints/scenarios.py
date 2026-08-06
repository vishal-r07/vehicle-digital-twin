"""
============================================================================
AutoTwin AI - Scenario Endpoints
============================================================================
Scenario engine control: start, stop, list scenarios.

Endpoints:
  GET   /api/scenarios              - List available scenarios
  GET   /api/scenarios/active       - Get active scenario status
  POST  /api/scenarios/{id}/start   - Start a scenario
  POST  /api/scenarios/{id}/stop    - Stop active scenario
  POST  /api/scenarios/pause        - Pause active scenario
  POST  /api/scenarios/resume       - Resume paused scenario
============================================================================
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class ScenarioStartRequest(BaseModel):
    speed_multiplier: float = 1.0


@router.get("")
async def list_scenarios(request: Request):
    """List all available scenarios."""
    scenario_engine = request.app.state.scenario_engine if hasattr(request.app.state, "scenario_engine") else None

    if not scenario_engine:
        from app.scenarios.scenario_definitions import ScenarioLibrary
        library = ScenarioLibrary()
        scenarios = [s.to_dict() for s in library.get_all()]
    else:
        scenarios = scenario_engine.get_available_scenarios()

    return {
        "success": True,
        "data": {
            "scenarios": scenarios,
            "count": len(scenarios),
        },
    }


@router.get("/active")
async def get_active_scenario(request: Request):
    """Get status of the currently active scenario."""
    scenario_engine = request.app.state.scenario_engine if hasattr(request.app.state, "scenario_engine") else None

    if not scenario_engine:
        return {"success": True, "data": {"scenario": None}}

    active = scenario_engine.get_active_scenario()
    return {
        "success": True,
        "data": {"scenario": active, "is_running": scenario_engine.is_running},
    }


@router.post("/{scenario_id}/start")
async def start_scenario(scenario_id: str, request: Request):
    """
    Start a scenario.

    Only one scenario can run at a time.
    """
    scenario_engine = request.app.state.scenario_engine if hasattr(request.app.state, "scenario_engine") else None

    if not scenario_engine:
        raise HTTPException(status_code=503, detail="Scenario engine not available")

    if scenario_engine.is_running:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "SCENARIO_ALREADY_ACTIVE",
                "message": "A scenario is already running. Stop it first.",
            },
        )

    success = await scenario_engine.start(scenario_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SCENARIO_NOT_FOUND",
                "message": f"Scenario '{scenario_id}' not found",
            },
        )

    return {
        "success": True,
        "data": {
            "scenario_id": scenario_id,
            "status": "started",
            "message": f"Scenario '{scenario_id}' started",
        },
    }


@router.post("/{scenario_id}/stop")
async def stop_scenario(scenario_id: str, request: Request):
    """Stop the active scenario."""
    scenario_engine = request.app.state.scenario_engine if hasattr(request.app.state, "scenario_engine") else None

    if not scenario_engine or not scenario_engine.is_running:
        return {
            "success": True,
            "data": {"message": "No scenario is running"},
        }

    await scenario_engine.stop()

    return {
        "success": True,
        "data": {
            "scenario_id": scenario_id,
            "status": "stopped",
        },
    }


@router.post("/pause")
async def pause_scenario(request: Request):
    """Pause the active scenario."""
    scenario_engine = request.app.state.scenario_engine if hasattr(request.app.state, "scenario_engine") else None

    if not scenario_engine or not scenario_engine.is_running:
        raise HTTPException(status_code=400, detail="No scenario is running")

    await scenario_engine.pause()
    return {"success": True, "data": {"status": "paused"}}


@router.post("/resume")
async def resume_scenario(request: Request):
    """Resume a paused scenario."""
    scenario_engine = request.app.state.scenario_engine if hasattr(request.app.state, "scenario_engine") else None

    if not scenario_engine:
        raise HTTPException(status_code=400, detail="No scenario engine")

    await scenario_engine.resume()
    return {"success": True, "data": {"status": "resumed"}}