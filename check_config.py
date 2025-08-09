#!/usr/bin/env python3
"""
Check current Pexels configuration
"""

from src.utils.env_utils import get_pexels_config
from src.config.settings import settings

def main():
    print("=== Current Pexels Configuration ===")
    
    # Get Pexels config
    pexels_config = get_pexels_config()
    
    print(f"Pexels Base URL: {pexels_config.get('pexels_base_url')}")
    print(f"Pexels Secret Key: {pexels_config.get('pexels_secret_key', 'Not set')[:10]}..." if pexels_config.get('pexels_secret_key') else "Not set")
    print(f"Request Frequency: {pexels_config.get('request_frequency')}")
    print(f"Resource Directory: {pexels_config.get('resource_dir')}")
    
    print("\n=== Settings Object ===")
    print(f"PEXELS_BASE_URL: {settings.pexels_base_url}")
    print(f"PEXELS_SECRET_KEY: {settings.pexels_secret_key[:10]}..." if settings.pexels_secret_key else "Not set")
    print(f"REQUEST_FREQUENCY: {settings.request_frequency}")
    print(f"RESOURCE_DIR: {settings.resource_dir}")
    
    print("\n=== Environment Check ===")
    import os
    print(f"PEXELS_BASE_URL env var: {os.getenv('PEXELS_BASE_URL')}")
    print(f"PEXELS_SECRET_KEY env var: {os.getenv('PEXELS_SECRET_KEY', 'Not set')[:10]}..." if os.getenv('PEXELS_SECRET_KEY') else "Not set")

if __name__ == "__main__":
    main()
