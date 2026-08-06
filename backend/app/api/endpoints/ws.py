"""
============================================================================
AutoTwin AI - WebSocket Endpoint & Connection Manager
============================================================================
Real-time data streaming to frontend clients.

WebSocket Protocol:
  Server → Client:
    - vehicle_state (20 Hz)
    - fault_event (on detection)
    - fault_resolved (on resolution)
    - health_update (periodic)
    - timeline_event (on log)
    - scenario_update (during scenarios)
    - connection_ack (on connect)
    - heartbeat (every 20s)

  Client → Server:
    - subscribe (channel selection)
    - request_state (full state request)
    - scenario_command
    - acknowledge_fault

Usage:
    Connect to: ws://localhost:8000/ws
============================================================================
"""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.constants import WSMessageType, EventType
from app.core.event_bus import Event, EventBus

router = APIRouter()


# ============================================================================
# WEBSOCKET MANAGER
# ============================================================================


class WebSocketManager:
    """
    Manages all WebSocket connections and broadcasts.

    Features:
      - Connection tracking
      - Broadcast to all clients
      - Per-client message queuing
      - Heartbeat/keepalive
      - Graceful disconnect handling
    """

    def __init__(self, settings=None):
        self._settings = settings
        self._connections: Dict[str, WebSocket] = {}
        self._client_subscriptions: Dict[str, Set[str]] = {}
        self._sequence: int = 0
        self._messages_sent: int = 0
        self._broadcast_task: Optional[asyncio.Task] = None
        self._running: bool = False

    @property
    def client_count(self) -> int:
        return len(self._connections)

    async def handle_connection(self, websocket: WebSocket) -> None:
        """Handle a new WebSocket connection lifecycle."""
        await websocket.accept()

        client_id = str(uuid.uuid4())[:8]
        self._connections[client_id] = websocket
        self._client_subscriptions[client_id] = {
            "vehicle_state", "fault_event", "fault_resolved",
            "health_update", "timeline_event", "scenario_update",
        }

        logger.info(f"WS: client connected ({client_id}), total: {self.client_count}")

        # Send connection acknowledgment
        await self._send_to_client(client_id, {
            "type": WSMessageType.CONNECTION_ACK.value,
            "seq": self._next_seq(),
            "timestamp": time.time(),
            "payload": {
                "client_id": client_id,
                "server_version": "1.0.0",
                "update_rate_hz": 20,
                "features": ["diagnostics", "scenarios", "replay", "health"],
            },
        })

        try:
            # Listen for incoming messages
            while True:
                data = await websocket.receive_text()
                await self._handle_client_message(client_id, data)

        except WebSocketDisconnect:
            logger.info(f"WS: client disconnected ({client_id})")
        except Exception as e:
            logger.error(f"WS: error with client {client_id}: {e}")
        finally:
            self._connections.pop(client_id, None)
            self._client_subscriptions.pop(client_id, None)
            logger.info(f"WS: client removed ({client_id}), total: {self.client_count}")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        if not self._connections:
            return

        message["seq"] = self._next_seq()
        if "timestamp" not in message:
            message["timestamp"] = time.time()

        # Determine message type for subscription filtering
        msg_type = message.get("type", "")

        disconnected = []
        for client_id, ws in self._connections.items():
            # Check subscription
            subs = self._client_subscriptions.get(client_id, set())
            if msg_type and msg_type not in subs and msg_type != "heartbeat":
                continue

            try:
                await ws.send_json(message)
                self._messages_sent += 1
            except Exception:
                disconnected.append(client_id)

        # Remove disconnected clients
        for client_id in disconnected:
            self._connections.pop(client_id, None)
            self._client_subscriptions.pop(client_id, None)

    async def broadcast_vehicle_state(self, state: Dict[str, Any]) -> None:
        """Broadcast vehicle state update."""
        await self.broadcast({
            "type": WSMessageType.VEHICLE_STATE.value,
            "payload": state,
        })

    async def broadcast_fault(self, fault_data: Dict[str, Any]) -> None:
        """Broadcast a fault event."""
        await self.broadcast({
            "type": WSMessageType.FAULT_EVENT.value,
            "payload": fault_data,
        })

    async def broadcast_health(self, health_data: Dict[str, Any]) -> None:
        """Broadcast health score update."""
        await self.broadcast({
            "type": WSMessageType.HEALTH_UPDATE.value,
            "payload": health_data,
        })

    async def close_all(self) -> None:
        """Close all WebSocket connections."""
        for client_id, ws in list(self._connections.items()):
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()
        self._client_subscriptions.clear()
        logger.info("WS: all connections closed")

    async def _send_to_client(self, client_id: str, message: Dict) -> None:
        """Send message to a specific client."""
        ws = self._connections.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
                self._messages_sent += 1
            except Exception as e:
                logger.error(f"WS: send error to {client_id}: {e}")

    async def _handle_client_message(self, client_id: str, data: str) -> None:
        """Handle incoming message from a client."""
        try:
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "subscribe":
                channels = message.get("payload", {}).get("channels", [])
                self._client_subscriptions[client_id] = set(channels)

            elif msg_type == "request_state":
                # Client requests full state snapshot
                # This would be handled by the broadcast service
                pass

            elif msg_type == "acknowledge_fault":
                fault_id = message.get("payload", {}).get("fault_id")
                if fault_id:
                    logger.info(f"WS: client {client_id} acknowledged fault {fault_id}")

        except json.JSONDecodeError:
            logger.warning(f"WS: invalid JSON from {client_id}")
        except Exception as e:
            logger.error(f"WS: message handling error: {e}")

    def _next_seq(self) -> int:
        self._sequence += 1
        return self._sequence

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active_connections": self.client_count,
            "messages_sent": self._messages_sent,
            "sequence": self._sequence,
        }