"""
============================================================================
AutoTwin AI - Vehicle Digital Twin Platform
============================================================================
Backend Application Package

This package contains the complete FastAPI backend for the AutoTwin AI
platform, providing:
  - Real-time vehicle state management via WebSocket
  - CAN frame parsing and decoding
  - Fault detection and diagnostics
  - Health score calculation
  - Scenario engine and replay
  - REST API for vehicle management

Architecture:
  Hardware → Serial Reader → CAN Parser → State Manager → WebSocket → Frontend

Version: 1.0.0
============================================================================
"""

__version__ = "1.0.0"
__app_name__ = "AutoTwin AI"
__author__ = "AutoTwin AI Development Team"
__license__ = "MIT"

# Expose key symbols for convenient imports
# Usage: from app import create_app, get_settings

from app.config import get_settings, Settings  # noqa: F401
from app.main import create_app  # noqa: F401