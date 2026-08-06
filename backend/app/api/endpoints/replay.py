"""
============================================================================
AutoTwin AI - Replay Endpoints
============================================================================
CAN log replay control.

Endpoints:
  GET   /api/replay/logs          - List available logs
  POST  /api/replay/start         - Start replay
  POST  /api/replay/pause         - Pause replay
  POST  /api/replay/resume        - Resume replay
  POST  /api/replay/stop          - Stop replay
  POST  /api/replay/seek          - Seek to position
  POST  /api/replay/speed         - Change playback speed
  GET   /api/replay/status        - Get replay status
============================================================================
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class ReplayStartRequest(BaseModel):
    log_id: str
    speed: float = 1.0


class ReplaySeekRequest(BaseModel):
    position_s: float


class ReplaySpeedRequest(BaseModel):
    speed: float


@router.get("/logs")
async def list_replay_logs(request: Request):
    """List available CAN log recordings."""
    # In production, this would scan the replay_logs_path directory
    # For now, return empty list or scan if configured
    from app.config import get_settings
    settings = get_settings()

    logs = []
    logs_path = settings.replay_logs_path
    if logs_path.exists():
        for f in logs_path.glob("*.json"):
            logs.append({
                "id": f.stem,
                "name": f.stem,
                "file_path": str(f),
                "size_bytes": f.stat().st_size,
            })

    return {
        "success": True,
        "data": {"logs": logs, "count": len(logs)},
    }


@router.post("/start")
async def start_replay(body: ReplayStartRequest, request: Request):
    """Start replaying a CAN log."""
    replay_engine = request.app.state.replay_engine if hasattr(request.app.state, "replay_engine") else None

    if not replay_engine:
        raise HTTPException(status_code=503, detail="Replay engine not available")

    # Load log
    from app.config import get_settings
    settings = get_settings()
    log_path = settings.replay_logs_path / f"{body.log_id}.json"

    if not log_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "REPLAY_LOG_NOT_FOUND", "message": f"Log '{body.log_id}' not found"},
        )

    loaded = await replay_engine.load(str(log_path))
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to load replay log")

    await replay_engine.play(speed=body.speed)

    return {
        "success": True,
        "data": {
            "log_id": body.log_id,
            "speed": body.speed,
            "status": "playing",
        },
    }


@router.post("/pause")
async def pause_replay(request: Request):
    """Pause replay."""
    replay_engine = request.app.state.replay_engine if hasattr(request.app.state, "replay_engine") else None
    if not replay_engine:
        raise HTTPException(status_code=400, detail="No replay active")

    await replay_engine.pause()
    return {"success": True, "data": {"status": "paused"}}


@router.post("/resume")
async def resume_replay(request: Request):
    """Resume paused replay."""
    replay_engine = request.app.state.replay_engine if hasattr(request.app.state, "replay_engine") else None
    if not replay_engine:
        raise HTTPException(status_code=400, detail="No replay active")

    await replay_engine.resume()
    return {"success": True, "data": {"status": "playing"}}


@router.post("/stop")
async def stop_replay(request: Request):
    """Stop replay."""
    replay_engine = request.app.state.replay_engine if hasattr(request.app.state, "replay_engine") else None
    if replay_engine:
        await replay_engine.stop()

    return {"success": True, "data": {"status": "stopped"}}


@router.post("/seek")
async def seek_replay(body: ReplaySeekRequest, request: Request):
    """Seek to a specific position in the replay."""
    replay_engine = request.app.state.replay_engine if hasattr(request.app.state, "replay_engine") else None
    if not replay_engine:
        raise HTTPException(status_code=400, detail="No replay active")

    await replay_engine.seek(body.position_s)
    return {
        "success": True,
        "data": {"position_s": body.position_s, "status": "seeked"},
    }


@router.post("/speed")
async def set_replay_speed(body: ReplaySpeedRequest, request: Request):
    """Change replay playback speed."""
    replay_engine = request.app.state.replay_engine if hasattr(request.app.state, "replay_engine") else None
    if not replay_engine:
        raise HTTPException(status_code=400, detail="No replay active")

    replay_engine.set_speed(body.speed)
    return {
        "success": True,
        "data": {"speed": body.speed},
    }


@router.get("/status")
async def get_replay_status(request: Request):
    """Get current replay status."""
    replay_engine = request.app.state.replay_engine if hasattr(request.app.state, "replay_engine") else None

    if not replay_engine:
        return {"success": True, "data": {"active": False}}

    return {
        "success": True,
        "data": replay_engine.get_stats(),
    }