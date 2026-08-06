"""
============================================================================
AutoTwin AI - Main API Router
============================================================================
Aggregates all endpoint routers under /api prefix.

Router Structure:
  /api/vehicles/*      → vehicles.py
  /api/diagnostics/*   → diagnostics.py
  /api/health/*        → health.py
  /api/scenarios/*     → scenarios.py
  /api/replay/*        → replay.py
  /api/system/*        → system.py
============================================================================
"""

from fastapi import APIRouter

from app.api.endpoints import vehicles, diagnostics, scenarios, replay, health, system

# ============================================================================
# MAIN API ROUTER
# ============================================================================

api_router = APIRouter()

# Mount sub-routers
api_router.include_router(
    vehicles.router,
    prefix="/vehicles",
    tags=["Vehicles"],
)

api_router.include_router(
    diagnostics.router,
    prefix="/diagnostics",
    tags=["Diagnostics"],
)

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

api_router.include_router(
    scenarios.router,
    prefix="/scenarios",
    tags=["Scenarios"],
)

api_router.include_router(
    replay.router,
    prefix="/replay",
    tags=["Replay"],
)

api_router.include_router(
    system.router,
    prefix="/system",
    tags=["System"],
)