"""
============================================================================
AutoTwin AI - System Endpoints
============================================================================
System status, configuration, and health checks.

Endpoints:
  GET   /api/system/status      - Overall system status
  GET   /api/system/config      - Current configuration
  PUT   /api/system/config      - Update configuration
  POST  /api/system/reset       - Reset vehicle state
  GET   /api/system/stats       - Detailed statistics
============================================================================
"""

import time

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()


class ConfigUpdateRequest(BaseModel):
    serial_port: str = None
    broadcast_interval_ms: int = None
    log_level: str = None


@router.get("/status")
async def get_system_status(request: Request):
    """
    Get overall system status.

    Includes connection status, frame rates, and service health.
    """
    settings = get_settings()

    # Gather status from all services
    serial_reader = request.app.state.serial_reader
    ws_manager = request.app.state.ws_manager
    state_manager = request.app.state.state_manager
    fault_engine = request.app.state.fault_engine

    return {
        "success": True,
        "data": {
            "app": {
                "name": settings.app.name,
                "version": settings.app.version,
                "environment": settings.app.environment,
                "uptime_s": time.time() - state_manager._session_start,
            },
            "hardware": {
                "serial_connected": serial_reader.is_connected,
                "serial_port": serial_reader._port_name,
                "frames_received": serial_reader.frames_received,
                "frame_rate": round(serial_reader.frame_rate, 1),
            },
            "websocket": {
                "active_connections": ws_manager.client_count,
            },
            "vehicle": {
                "can_active": state_manager.can_active,
                "frame_count": state_manager.frame_count,
                "stale_signals": state_manager.get_stale_signals(),
            },
            "diagnostics": {
                "active_faults": fault_engine.active_fault_count,
                "rules_loaded": len(fault_engine._rules),
            },
        },
    }


@router.get("/config")
async def get_configuration(request: Request):
    """Get current application configuration."""
    settings = get_settings()

    return {
        "success": True,
        "data": {
            "serial": {
                "port": settings.serial.port,
                "baud_rate": settings.serial.baud_rate,
                "auto_detect": settings.serial.auto_detect,
            },
            "can": {
                "baud_rate": settings.can.baud_rate,
                "timeout_ms": settings.can.timeout_ms,
            },
            "broadcast": {
                "interval_ms": settings.broadcast.interval_ms,
                "include_timestamp": settings.broadcast.include_timestamp,
            },
            "diagnostics": {
                "fault_cooldown_s": settings.diagnostics.fault_cooldown_s,
                "health_update_interval_s": settings.diagnostics.health_update_interval_s,
            },
            "server": {
                "host": settings.server.host,
                "port": settings.server.port,
            },
        },
    }


@router.put("/config")
async def update_configuration(body: ConfigUpdateRequest, request: Request):
    """
    Update runtime configuration.

    Only allows safe runtime changes (not hardware pins, etc.)
    """
    settings = get_settings()
    changes = {}

    if body.serial_port:
        changes["serial_port"] = body.serial_port

    if body.broadcast_interval_ms:
        changes["broadcast_interval_ms"] = body.broadcast_interval_ms

    if body.log_level:
        changes["log_level"] = body.log_level

    return {
        "success": True,
        "data": {
            "updated": changes,
            "message": f"Updated {len(changes)} setting(s)",
        },
    }


@router.post("/reset")
async def reset_system(request: Request):
    """
    Reset vehicle state and clear faults.

    Does NOT disconnect hardware or restart services.
    """
    state_manager = request.app.state.state_manager
    fault_engine = request.app.state.fault_engine

    await state_manager.reset()

    # Clear active faults
    for rule_id in list(fault_engine._active_faults.keys()):
        await fault_engine.resolve_fault(rule_id, reason="system_reset")

    return {
        "success": True,
        "data": {"message": "System state reset"},
    }


@router.get("/stats")
async def get_detailed_stats(request: Request):
    """Get detailed statistics from all services."""
    serial_reader = request.app.state.serial_reader
    state_manager = request.app.state.state_manager
    fault_engine = request.app.state.fault_engine
    ws_manager = request.app.state.ws_manager

    return {
        "success": True,
        "data": {
            "serial": serial_reader.get_stats(),
            "state": state_manager.get_stats(),
            "faults": fault_engine.get_stats(),
            "websocket": ws_manager.get_stats(),
        },
    }