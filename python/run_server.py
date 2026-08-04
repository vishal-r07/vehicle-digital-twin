#!/usr/bin/env python3
"""
run_server.py - Convenience script to launch the backend.

Usage:
    python run_server.py
    python run_server.py --port COM5
    python run_server.py --ws-port 9000
"""

import argparse
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.main import run
from backend.config import config


def parse_args():
    parser = argparse.ArgumentParser(
        description="Vehicle Digital Twin - Phase 1 Backend Server"
    )
    parser.add_argument(
        '--port', type=str, default=None,
        help='Serial port (e.g., COM3, /dev/ttyACM0)'
    )
    parser.add_argument(
        '--ws-port', type=int, default=None,
        help='WebSocket server port (default: 8765)'
    )
    parser.add_argument(
        '--log-level', type=str, default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level'
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    if args.port:
        config.serial.port = args.port
    if args.ws_port:
        config.websocket.port = args.ws_port
    config.log_level = args.log_level
    
    print(f"""
    +--------------------------------------------------+
    |   Vehicle Digital Twin - Phase 1 Backend         |
    |                                                  |
    |   Serial Port:  {config.serial.port:<32} |
    |   Baud Rate:    {config.serial.baud_rate:<32} |
    |   WebSocket:    ws://0.0.0.0:{config.websocket.port:<19} |
    |   Log Level:    {config.log_level:<32} |
    +--------------------------------------------------+
    """)
    
    run()