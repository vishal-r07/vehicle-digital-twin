"""
websocket_server.py - WebSocket server for real-time data broadcast

Serves vehicle data to all connected React/Three.js clients.
Handles connection management, heartbeat, and graceful shutdown.

Future: Add authentication, room-based subscriptions (fleet monitoring),
        message history for late-joining clients.
"""

import asyncio
import json
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Set
from datetime import datetime, timezone

from .config import config
from .utils.logger import setup_logger

logger = setup_logger("WebSocket")


class WebSocketServer:
    """
    Async WebSocket server for broadcasting vehicle telemetry.
    
    Clients connect to ws://host:port and receive JSON updates at ~20Hz.
    """
    
    def __init__(self):
        self._clients: Set[WebSocketServerProtocol] = set()
        self._server = None
        self._running: bool = False
        self._ws_config = config.websocket
        self._latest_data: Optional[dict] = None
    
    @property
    def client_count(self) -> int:
        return len(self._clients)
    
    async def start(self):
        """Start the WebSocket server."""
        self._running = True
        self._server = await websockets.serve(
            self._handler,
            self._ws_config.host,
            self._ws_config.port,
            ping_interval=self._ws_config.ping_interval,
            ping_timeout=self._ws_config.ping_timeout,
        )
        logger.info(
            f"WebSocket server started on "
            f"ws://{self._ws_config.host}:{self._ws_config.port}"
        )
    
    async def stop(self):
        """Gracefully stop the server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        # Close all client connections
        for client in self._clients.copy():
            await client.close()
        self._clients.clear()
        
        logger.info("WebSocket server stopped")
    
    async def broadcast(self, data: dict):
        """Broadcast vehicle data to all connected clients."""
        if not self._clients:
            return
        
        self._latest_data = data
        message = json.dumps(data)
        
        # Send to all clients, remove disconnected ones
        disconnected = set()
        for client in self._clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
                disconnected.add(client)
        
        # Clean up disconnected clients
        self._clients -= disconnected
        if disconnected:
            logger.info(f"Removed {len(disconnected)} disconnected client(s)")
    
    async def _handler(self, websocket: WebSocketServerProtocol, path: str = "/"):
        """Handle new WebSocket client connection."""
        remote = websocket.remote_address
        logger.info(f"Client connected: {remote} (total: {len(self._clients) + 1})")
        self._clients.add(websocket)
        
        try:
            # Send latest data immediately to new client
            if self._latest_data:
                await websocket.send(json.dumps(self._latest_data))
            
            # Send connection acknowledgment
            await websocket.send(json.dumps({
                "type": "connection",
                "status": "connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "update_rate_hz": 20
            }))
            
            # Keep connection alive, handle incoming messages
            async for message in websocket:
                # Future: Handle client commands (e.g., subscribe to specific signals)
                try:
                    cmd = json.loads(message)
                    logger.debug(f"Client command: {cmd}")
                except json.JSONDecodeError:
                    pass
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            logger.info(f"Client disconnected: {remote} (total: {len(self._clients)})")


# Type hint fix
from typing import Optional