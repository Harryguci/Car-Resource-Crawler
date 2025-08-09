#!/usr/bin/env python3
"""
Startup script for FastAPI application with environment variable support
"""
import uvicorn
from src.config.settings import settings
from src.config.logging_config import setup_logging, get_logger
import os

def main():
    """Main function to start the FastAPI application"""
    
    # Setup logging first
    setup_logging()
    logger = get_logger(__name__)
    
    # Log environment information
    logger.info(f"Starting {settings.app_name} v{settings.version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Host: {settings.host}")
    logger.info(f"Port: {settings.port}")
    logger.info(f"Log file: {settings.log_file}")
    
    # Validate required environment variables
    from src.utils.env_utils import validate_required_env_vars
    validation_results = validate_required_env_vars()

    if not all(validation_results.values()):
        logger.warning("Some required environment variables are not set:")
        for var, valid in validation_results.items():
            if not valid:
                logger.warning(f"   - {var}")
        logger.warning("Check your .env file or environment variables.")
    
    # Start the server
    logger.info("Starting FastAPI server...")
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )

if __name__ == "__main__":
    main()
