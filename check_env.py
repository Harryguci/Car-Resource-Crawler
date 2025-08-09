#!/usr/bin/env python3
"""
Check environment variables and configuration
"""

import os
from src.config.settings import settings

def main():
    print("=== Environment Variables Check ===")
    
    # Check if .env file exists
    env_file_exists = os.path.exists('.env')
    print(f".env file exists: {'✅' if env_file_exists else '❌'}")
    
    # Check Pexels environment variables
    pexels_base_url = os.getenv('PEXELS_BASE_URL')
    pexels_secret_key = os.getenv('PEXELS_SECRET_KEY')
    
    print(f"PEXELS_BASE_URL: {pexels_base_url if pexels_base_url else '❌ Not set'}")
    print(f"PEXELS_SECRET_KEY: {pexels_secret_key[:10] + '...' if pexels_secret_key else '❌ Not set'}")
    
    print("\n=== Settings Object ===")
    print(f"settings.pexels_base_url: {settings.pexels_base_url}")
    print(f"settings.pexels_secret_key: {settings.pexels_secret_key[:10] + '...' if settings.pexels_secret_key else '❌ Not set'}")
    print(f"settings.request_frequency: {settings.request_frequency}")
    print(f"settings.resource_dir: {settings.resource_dir}")
    
    print("\n=== Recommendations ===")
    if not env_file_exists:
        print("1. Create .env file: cp env.example .env")
        print("2. Edit .env file with your Pexels API credentials")
    
    if not pexels_secret_key:
        print("3. Set PEXELS_SECRET_KEY in your .env file")
        print("   Example: PEXELS_SECRET_KEY=your_secret_key_here")
    
    if not pexels_base_url:
        print("4. Set PEXELS_BASE_URL in your .env file")
        print("   Example: PEXELS_BASE_URL=https://www.pexels.com/en-us/api/v3")

if __name__ == "__main__":
    main()
