#!/usr/bin/env python3
"""
Test script to verify logging configuration
"""
from src.config.logging_config import setup_logging, get_logger
import time

def test_logging():
    """Test the logging configuration"""
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)
    
    # Test different log levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Test with different modules
    test_logger = get_logger("test_module")
    test_logger.info("This is a test message from test_module")
    
    print("Logging test completed. Check logs/log.txt for output.")

if __name__ == "__main__":
    test_logging()
