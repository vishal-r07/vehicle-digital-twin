"""
main.py - Application entry point for Vehicle Digital Twin Backend
"""

import asyncio
import signal
import sys

from .services.broadcast_service import BroadcastService
from .utils.logger import setup_logger

logger = setup_logger("Main")


async def main():
    """Main application coroutine."""
    service = BroadcastService()
    
    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    
    def shutdown_handler(sig, frame):
        logger.info(f"\nReceived signal {sig}. Shutting down...")
        asyncio.ensure_future(service.stop())
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    try:
        await service.start()
    except KeyboardInterrupt:
        pass
    finally:
        await service.stop()


def run():
    """Entry point."""
    logger.info("Starting Vehicle Digital Twin Backend...")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete.")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()