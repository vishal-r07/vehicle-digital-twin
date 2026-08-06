"""
============================================================================
AutoTwin AI - FastAPI Application Entry Point
============================================================================
Creates and configures the FastAPI application with:
  - Lifespan management (startup/shutdown)
  - Middleware (CORS, logging, error handling)
  - Router mounting (REST + WebSocket)
  - Background task management
  - Graceful shutdown handling

Usage:
    # Development
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

    # Production
    gunicorn app.main:app -w 1 -k uvicorn.workers.UvicornWorker

    # Or use entry points
    autotwin          # Production mode
    autotwin-dev      # Development mode with reload
============================================================================
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from loguru import logger

from app.config import get_settings


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================


def configure_logging(settings) -> None:
    """Configure loguru logging for the application."""
    logger.remove()  # Remove default handler

    # Console output
    logger.add(
        sys.stdout,
        level=settings.app.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File output (rotating)
    logger.add(
        "logs/autotwin_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    )


# ============================================================================
# LIFESPAN MANAGER
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Startup:
      1. Load configuration
      2. Initialize database
      3. Load vehicle plugins
      4. Start serial reader
      5. Start WebSocket manager
      6. Start background tasks

    Shutdown:
      1. Stop background tasks
      2. Stop serial reader
      3. Close WebSocket connections
      4. Flush database
      5. Cleanup resources
    """
    settings = get_settings()
    logger.info("=" * 60)
    logger.info(f"  {settings.app.name} v{settings.app.version}")
    logger.info(f"  {settings.app.description}")
    logger.info("=" * 60)

    # --- STARTUP ---
    logger.info("[STARTUP] Initializing application...")

    # Import and initialize core services
    from app.core.event_bus import EventBus
    from app.core.state_manager import VehicleStateManager
    from app.hardware.serial_reader import SerialReader
    from app.can.frame_parser import CANFrameParser
    from app.diagnostics.fault_engine import FaultEngine
    from app.vehicle.health_calculator import HealthCalculator
    from app.services.broadcast_service import BroadcastService
    from app.api.endpoints.ws import WebSocketManager

    # Initialize Event Bus (internal pub/sub)
    event_bus = EventBus()
    app.state.event_bus = event_bus
    logger.info("[STARTUP] Event bus initialized")

    # Initialize Vehicle State Manager
    state_manager = VehicleStateManager(event_bus)
    app.state.state_manager = state_manager
    logger.info("[STARTUP] Vehicle State Manager initialized")

    # Initialize CAN Frame Parser
    can_parser = CANFrameParser()
    app.state.can_parser = can_parser
    logger.info("[STARTUP] CAN Frame Parser initialized")

    # Initialize Fault Detection Engine
    fault_engine = FaultEngine(event_bus, settings.diagnostics)
    app.state.fault_engine = fault_engine
    logger.info("[STARTUP] Fault Detection Engine initialized")

    # Initialize Health Calculator
    health_calculator = HealthCalculator(event_bus)
    app.state.health_calculator = health_calculator
    logger.info("[STARTUP] Health Calculator initialized")

    # Initialize WebSocket Manager
    ws_manager = WebSocketManager(settings.websocket)
    app.state.ws_manager = ws_manager
    logger.info("[STARTUP] WebSocket Manager initialized")

    # Initialize Broadcast Service
    broadcast_service = BroadcastService(
        state_manager=state_manager,
        ws_manager=ws_manager,
        event_bus=event_bus,
        settings=settings.broadcast,
    )
    app.state.broadcast_service = broadcast_service
    logger.info("[STARTUP] Broadcast Service initialized")

    # Initialize Serial Reader
    serial_reader = SerialReader(settings.serial, event_bus)
    app.state.serial_reader = serial_reader
    logger.info("[STARTUP] Serial Reader initialized")

    # Load vehicle plugins
    from app.services.vehicle_service import VehicleService
    vehicle_service = VehicleService(settings.vehicle)
    app.state.vehicle_service = vehicle_service
    vehicle_count = vehicle_service.load_registry()
    logger.info(f"[STARTUP] Loaded {vehicle_count} vehicle plugin(s)")

    # Start services
    await serial_reader.start()
    logger.info("[STARTUP] Serial reader started")

    await broadcast_service.start()
    logger.info("[STARTUP] Broadcast service started")

    await fault_engine.start()
    logger.info("[STARTUP] Fault engine started")

    # Start health calculator periodic task
    health_task = asyncio.create_task(
        health_calculator.periodic_update(settings.diagnostics.health_update_interval_s)
    )
    app.state.health_task = health_task

    logger.info("[STARTUP] ✓ All services started successfully")
    logger.info(f"[STARTUP] Server: {settings.server.base_url}")
    logger.info(f"[STARTUP] WebSocket: ws://{settings.server.host}:{settings.server.port}/ws")
    logger.info(f"[STARTUP] API Docs: {settings.server.base_url}/docs")
    logger.info("=" * 60)

    # --- YIELD (Application running) ---
    yield

    # --- SHUTDOWN ---
    logger.info("[SHUTDOWN] Stopping application...")

    # Cancel health task
    if hasattr(app.state, "health_task"):
        app.state.health_task.cancel()
        try:
            await app.state.health_task
        except asyncio.CancelledError:
            pass

    # Stop broadcast service
    await broadcast_service.stop()
    logger.info("[SHUTDOWN] Broadcast service stopped")

    # Stop serial reader
    await serial_reader.stop()
    logger.info("[SHUTDOWN] Serial reader stopped")

    # Stop fault engine
    await fault_engine.stop()
    logger.info("[SHUTDOWN] Fault engine stopped")

    # Close all WebSocket connections
    await ws_manager.close_all()
    logger.info("[SHUTDOWN] WebSocket connections closed")

    # Flush event bus
    await event_bus.shutdown()
    logger.info("[SHUTDOWN] Event bus shut down")

    logger.info("[SHUTDOWN] ✓ Application stopped cleanly")


# ============================================================================
# APPLICATION FACTORY
# ============================================================================


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        description=settings.app.description,
        lifespan=lifespan,
        docs_url="/docs" if settings.app.debug else None,
        redoc_url="/redoc" if settings.app.debug else None,
        openapi_url="/openapi.json" if settings.app.debug else None,
        default_response_class=ORJSONResponse,  # Faster JSON serialization
    )

    # --- MIDDLEWARE ---

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        logger.debug(f"→ {request.method} {request.url.path}")
        response = await call_next(request)
        logger.debug(f"← {response.status_code} {request.method} {request.url.path}")
        return response

    # --- ERROR HANDLERS ---

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal server error occurred",
                },
            },
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Resource not found: {request.url.path}",
                },
            },
        )

    # --- ROUTERS ---

    from app.api.router import api_router
    app.include_router(api_router, prefix="/api")

    # --- WEBSOCKET ENDPOINT ---

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """Main WebSocket endpoint for real-time vehicle data."""
        ws_manager: WebSocketManager = app.state.ws_manager
        await ws_manager.handle_connection(websocket)

    # --- HEALTH CHECK ---

    @app.get("/health", tags=["System"])
    async def health_check():
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "version": settings.app.version,
            "services": {
                "serial": app.state.serial_reader.is_connected if hasattr(app.state, "serial_reader") else False,
                "websocket_clients": app.state.ws_manager.client_count if hasattr(app.state, "ws_manager") else 0,
            },
        }

    @app.get("/", tags=["System"])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": settings.app.name,
            "version": settings.app.version,
            "description": settings.app.description,
            "docs": "/docs",
            "websocket": "/ws",
            "api": "/api",
        }

    return app


# ============================================================================
# APPLICATION INSTANCE
# ============================================================================

app = create_app()


# ============================================================================
# ENTRY POINTS
# ============================================================================


def run() -> None:
    """Production entry point."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        log_level=settings.app.log_level.lower(),
    )


def run_dev() -> None:
    """Development entry point with auto-reload."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
        log_level="debug",
    )


if __name__ == "__main__":
    run_dev()