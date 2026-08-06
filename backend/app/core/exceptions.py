"""
============================================================================
AutoTwin AI - Custom Exception Hierarchy
============================================================================
Structured exceptions for all error conditions.
Each exception carries a machine-readable code and optional details.

Usage:
    raise VehicleNotFoundError("toyota_corolla_2020")

    # In FastAPI exception handler:
    @app.exception_handler(AutoTwinError)
    async def handle_autotwin_error(request, exc):
        return JSONResponse(status_code=400, content={
            "success": False,
            "error": {"code": exc.code, "message": exc.message, "details": exc.details}
        })
============================================================================
"""

from typing import Any, Dict, Optional


# ============================================================================
# BASE EXCEPTION
# ============================================================================


class AutoTwinError(Exception):
    """
    Base exception for all AutoTwin AI errors.

    Attributes:
        message: Human-readable error description
        code: Machine-readable error code (for frontend handling)
        details: Additional structured error context
    """

    status_code: int = 500  # HTTP status code for API responses

    def __init__(
        self,
        message: str,
        code: str = "AUTOTWIN_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ============================================================================
# HARDWARE / CONNECTION ERRORS (status 503)
# ============================================================================


class SerialConnectionError(AutoTwinError):
    """Failed to connect to STM32 via serial port."""
    status_code = 503

    def __init__(self, port: str, reason: str = ""):
        super().__init__(
            message=f"Serial connection failed on '{port}': {reason}",
            code="SERIAL_CONNECTION_ERROR",
            details={"port": port, "reason": reason},
        )


class SerialTimeoutError(AutoTwinError):
    """Serial read timed out."""
    status_code = 503

    def __init__(self, port: str, timeout_s: float):
        super().__init__(
            message=f"Serial read timeout on '{port}' after {timeout_s}s",
            code="SERIAL_TIMEOUT",
            details={"port": port, "timeout_s": timeout_s},
        )


class CANConnectionError(AutoTwinError):
    """CAN bus connection failure."""
    status_code = 503

    def __init__(self, reason: str = ""):
        super().__init__(
            message=f"CAN bus error: {reason}",
            code="CAN_CONNECTION_ERROR",
            details={"reason": reason},
        )


class CANBusOffError(AutoTwinError):
    """CAN bus entered bus-off state."""
    status_code = 503

    def __init__(self):
        super().__init__(
            message="CAN bus is in bus-off state. Recovery in progress.",
            code="CAN_BUS_OFF",
        )


class CANFrameError(AutoTwinError):
    """Malformed or undecodable CAN frame."""
    status_code = 422

    def __init__(self, can_id: int, reason: str = ""):
        super().__init__(
            message=f"CAN frame error (ID=0x{can_id:03X}): {reason}",
            code="CAN_FRAME_ERROR",
            details={"can_id": can_id, "reason": reason},
        )


# ============================================================================
# VEHICLE / PLUGIN ERRORS (status 404)
# ============================================================================


class VehicleNotFoundError(AutoTwinError):
    """Requested vehicle not found in registry."""
    status_code = 404

    def __init__(self, slug: str):
        super().__init__(
            message=f"Vehicle '{slug}' not found",
            code="VEHICLE_NOT_FOUND",
            details={"slug": slug},
        )


class VehiclePluginError(AutoTwinError):
    """Vehicle plugin failed to load or validate."""
    status_code = 500

    def __init__(self, slug: str, reason: str):
        super().__init__(
            message=f"Vehicle plugin '{slug}' error: {reason}",
            code="VEHICLE_PLUGIN_ERROR",
            details={"slug": slug, "reason": reason},
        )


class VehicleNotSelectedError(AutoTwinError):
    """Operation requires a vehicle to be selected."""
    status_code = 400

    def __init__(self):
        super().__init__(
            message="No vehicle selected. Select a vehicle first.",
            code="VEHICLE_NOT_SELECTED",
        )


# ============================================================================
# SIGNAL / PARSING ERRORS (status 422)
# ============================================================================


class InvalidSignalError(AutoTwinError):
    """Signal value is invalid or out of range."""
    status_code = 422

    def __init__(self, signal_name: str, value: Any, reason: str = ""):
        super().__init__(
            message=f"Invalid signal '{signal_name}': {value} ({reason})",
            code="INVALID_SIGNAL",
            details={"signal": signal_name, "value": str(value), "reason": reason},
        )


class SignalNotFoundError(AutoTwinError):
    """Referenced signal does not exist."""
    status_code = 404

    def __init__(self, signal_name: str):
        super().__init__(
            message=f"Signal '{signal_name}' not found",
            code="SIGNAL_NOT_FOUND",
            details={"signal": signal_name},
        )


class DBCParseError(AutoTwinError):
    """DBC file parsing failed."""
    status_code = 500

    def __init__(self, file_path: str, reason: str = ""):
        super().__init__(
            message=f"DBC parse error in '{file_path}': {reason}",
            code="DBC_PARSE_ERROR",
            details={"file": file_path, "reason": reason},
        )


# ============================================================================
# DIAGNOSTIC ERRORS (status 400/404)
# ============================================================================


class FaultRuleError(AutoTwinError):
    """Fault rule definition or evaluation error."""
    status_code = 500

    def __init__(self, rule_id: str, reason: str = ""):
        super().__init__(
            message=f"Fault rule '{rule_id}' error: {reason}",
            code="FAULT_RULE_ERROR",
            details={"rule_id": rule_id, "reason": reason},
        )


class FaultNotFoundError(AutoTwinError):
    """Referenced fault event not found."""
    status_code = 404

    def __init__(self, fault_id: str):
        super().__init__(
            message=f"Fault '{fault_id}' not found",
            code="FAULT_NOT_FOUND",
            details={"fault_id": fault_id},
        )


class FaultAlreadyAcknowledgedError(AutoTwinError):
    """Fault was already acknowledged."""
    status_code = 409

    def __init__(self, fault_id: str):
        super().__init__(
            message=f"Fault '{fault_id}' already acknowledged",
            code="FAULT_ALREADY_ACKNOWLEDGED",
            details={"fault_id": fault_id},
        )


# ============================================================================
# SCENARIO ERRORS (status 400/404/409)
# ============================================================================


class ScenarioNotFoundError(AutoTwinError):
    """Requested scenario not found."""
    status_code = 404

    def __init__(self, scenario_id: str):
        super().__init__(
            message=f"Scenario '{scenario_id}' not found",
            code="SCENARIO_NOT_FOUND",
            details={"scenario_id": scenario_id},
        )


class ScenarioAlreadyActiveError(AutoTwinError):
    """Another scenario is already running."""
    status_code = 409

    def __init__(self, active_scenario: str):
        super().__init__(
            message=f"Scenario '{active_scenario}' is already active",
            code="SCENARIO_ALREADY_ACTIVE",
            details={"active_scenario": active_scenario},
        )


class ScenarioError(AutoTwinError):
    """General scenario execution error."""
    status_code = 500

    def __init__(self, scenario_id: str, reason: str):
        super().__init__(
            message=f"Scenario '{scenario_id}' error: {reason}",
            code="SCENARIO_ERROR",
            details={"scenario_id": scenario_id, "reason": reason},
        )


# ============================================================================
# REPLAY ERRORS (status 400/404)
# ============================================================================


class ReplayLogNotFoundError(AutoTwinError):
    """Requested replay log not found."""
    status_code = 404

    def __init__(self, log_id: str):
        super().__init__(
            message=f"Replay log '{log_id}' not found",
            code="REPLAY_LOG_NOT_FOUND",
            details={"log_id": log_id},
        )


class ReplayError(AutoTwinError):
    """General replay engine error."""
    status_code = 500

    def __init__(self, reason: str):
        super().__init__(
            message=f"Replay error: {reason}",
            code="REPLAY_ERROR",
            details={"reason": reason},
        )


class ReplayNotActiveError(AutoTwinError):
    """Replay operation attempted while no replay is active."""
    status_code = 400

    def __init__(self):
        super().__init__(
            message="No replay is currently active",
            code="REPLAY_NOT_ACTIVE",
        )


# ============================================================================
# WEBSOCKET ERRORS (status 400)
# ============================================================================


class WebSocketError(AutoTwinError):
    """WebSocket communication error."""
    status_code = 400

    def __init__(self, reason: str):
        super().__init__(
            message=f"WebSocket error: {reason}",
            code="WEBSOCKET_ERROR",
            details={"reason": reason},
        )


class WebSocketMessageError(AutoTwinError):
    """Invalid WebSocket message format."""
    status_code = 422

    def __init__(self, reason: str):
        super().__init__(
            message=f"Invalid WebSocket message: {reason}",
            code="WEBSOCKET_MESSAGE_ERROR",
            details={"reason": reason},
        )


# ============================================================================
# DATABASE ERRORS (status 500)
# ============================================================================


class DatabaseError(AutoTwinError):
    """Database operation failure."""
    status_code = 500

    def __init__(self, operation: str, reason: str = ""):
        super().__init__(
            message=f"Database error during '{operation}': {reason}",
            code="DATABASE_ERROR",
            details={"operation": operation, "reason": reason},
        )


class MigrationError(AutoTwinError):
    """Database migration failure."""
    status_code = 500

    def __init__(self, revision: str, reason: str):
        super().__init__(
            message=f"Migration '{revision}' failed: {reason}",
            code="MIGRATION_ERROR",
            details={"revision": revision, "reason": reason},
        )


# ============================================================================
# CONFIGURATION ERRORS (status 500)
# ============================================================================


class ConfigurationError(AutoTwinError):
    """Invalid or missing configuration."""
    status_code = 500

    def __init__(self, key: str, reason: str = ""):
        super().__init__(
            message=f"Configuration error for '{key}': {reason}",
            code="CONFIGURATION_ERROR",
            details={"key": key, "reason": reason},
        )


class FileNotFoundError_(AutoTwinError):
    """Required file not found."""
    status_code = 500

    def __init__(self, file_path: str, context: str = ""):
        super().__init__(
            message=f"File not found: '{file_path}' ({context})",
            code="FILE_NOT_FOUND",
            details={"file": file_path, "context": context},
        )