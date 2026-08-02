"""
logger.py - Centralized logging configuration
"""

import logging
import sys
from datetime import datetime


def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Configure and return a logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    if not logger.handlers:
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        # Format
        formatter = logging.Formatter(
            fmt='[%(asctime)s] %(levelname)-8s %(name)-15s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger