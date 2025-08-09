#!/usr/bin/env python3
"""
Startup script for FastAPI application with environment variable support
"""
import uvicorn
from src.config.settings import settings
import os

def main():
    """Main function to start the FastAPI application"""
    
    # Print environment information
    print(f"Starting {settings.app_name} v{settings.version}")
    print(f"Environment: {settings.environment}")
    print(f"Debug mode: {settings.debug}")
    print(f"Host: {settings.host}")
    print(f"Port: {settings.port}")
    
    # Validate required environment variables
    from src.utils.env_utils import validate_required_env_vars
    validation_results = validate_required_env_vars()

    if not all(validation_results.values()):
        print("⚠️  Warning: Some required environment variables are not set:")
        for var, valid in validation_results.items():
            if not valid:
                print(f"   - {var}")
        print("   Check your .env file or environment variables.")
    
    # Start the server
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )

if __name__ == "__main__":
    main()
