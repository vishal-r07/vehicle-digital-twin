"""
============================================================================
AutoTwin AI - API Module
============================================================================
REST API and WebSocket endpoints for the AutoTwin AI platform.

Endpoints:
  /api/vehicles       - Vehicle selection and management
  /api/diagnostics    - Fault queries and management
  /api/health         - Health scores and trends
  /api/scenarios      - Scenario engine control
  /api/replay         - CAN log replay control
  /api/system         - System status and configuration
  /ws                 - WebSocket real-time data stream

Documentation:
  - Interactive docs: /docs (Swagger UI)
  - Alternative docs: /redoc
  - OpenAPI schema: /openapi.json
============================================================================
"""

from app.api.router import api_router  # noqa: F401

__all__ = ["api_router"]