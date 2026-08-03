"""
broadcast_service.py - Orchestrates data flow from serial to WebSocket

This is the main service loop that:
1. Reads frames from serial
2. Parses and validates data
3. Broadcasts to WebSocket clients

Future: Add database writes, MQTT publishing, ML inference triggers.
"""

import asyncio
import time
from typing import Optional

from ..config import config
from ..serial_reader import SerialReader
from ..data_parser import DataParser
from ..websocket_server import WebSocketServer
from ..models.vehicle_data import VehicleData
from ..utils.logger import setup_logger

logger = setup_logger("BroadcastService")


class BroadcastService:
    """
    Main orchestration service.
    
    Data Flow:
        SerialReader → DataParser → WebSocketServer → Clients
    """
    
    def __init__(self):
        self._serial_reader = SerialReader()
        self._parser = DataParser()
        self._ws_server = WebSocketServer()
        self._running: bool = False
        self._broadcast_interval = config.broadcast_interval_ms / 1000.0
    
    async def start(self):
        """Start all services."""
        logger.info("=" * 60)
        logger.info("  Vehicle Digital Twin - Phase 1 Backend")
        logger.info("=" * 60)
        
        # Start WebSocket server
        await self._ws_server.start()
        
        # Start serial reader
        self._serial_reader.start()
        
        self._running = True
        logger.info("All services started. Broadcasting vehicle data...")
        
        # Main broadcast loop
        await self._broadcast_loop()
    
    async def stop(self):
        """Stop all services gracefully."""
        self._running = False
        self._serial_reader.stop()
        self._serial_reader.disconnect()
        await self._ws_server.stop()
        logger.info("All services stopped.")
    
    async def _broadcast_loop(self):
        """Main loop: read serial → parse → broadcast."""
        while self._running:
            try:
                # Read frame from serial (non-blocking via queue)
                raw_frame = self._serial_reader.get_frame(timeout=0.05)
                
                if raw_frame:
                    # Parse and validate
                    vehicle_data = self._parser.parse(raw_frame)
                    
                    if vehicle_data:
                        # Check for warnings
                        warnings = self._parser.get_warnings(vehicle_data)
                        for w in warnings:
                            logger.warning(w)
                        
                        # Broadcast to all WebSocket clients
                        await self._ws_server.broadcast(vehicle_data.to_dict())
                
                # Yield to event loop
                await asyncio.sleep(self._broadcast_interval)
                
            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")
                await asyncio.sleep(1.0)