#!/usr/bin/env python3
"""
Simple environment variables check without dependencies
"""

import os
from pathlib import Path

def main():
    print("=== Simple Environment Variables Check ===")
    
    # Check if .env file exists
    env_file_path = Path('.env')
    env_file_exists = env_file_path.exists()
    print(f".env file exists: {'✅' if env_file_exists else '❌'}")
    
    if env_file_exists:
        print(f".env file size: {env_file_path.stat().st_size} bytes")
        
        # Try to read the .env file content
        try:
            with open('.env', 'r', encoding='utf-8') as f:
                content = f.read()
                print(f".env file content preview:")
                print("=" * 50)
                for line in content.split('\n')[:10]:  # Show first 10 lines
                    if line.strip() and not line.strip().startswith('#'):
                        # Hide sensitive values
                        if 'SECRET' in line or 'KEY' in line or 'PASSWORD' in line:
                            key, *value_parts = line.split('=', 1)
                            if len(value_parts) > 0:
                                value = value_parts[0]
                                if value:
                                    print(f"{key}={value[:10]}..." if len(value) > 10 else f"{key}={value}")
                                else:
                                    print(f"{key}=")
                            else:
                                print(f"{key}=")
                        else:
                            print(line)
                print("=" * 50)
        except Exception as e:
            print(f"Error reading .env file: {e}")
    
    # Check environment variables directly
    print("\n=== Environment Variables ===")
    pexels_base_url = os.getenv('PEXELS_BASE_URL')
    pexels_secret_key = os.getenv('PEXELS_SECRET_KEY')
    
    print(f"PEXELS_BASE_URL: {pexels_base_url if pexels_base_url else '❌ Not set'}")
    print(f"PEXELS_SECRET_KEY: {pexels_secret_key[:10] + '...' if pexels_secret_key else '❌ Not set'}")
    
    # Check if python-dotenv is available and try to load .env manually
    print("\n=== Manual .env Loading Test ===")
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv is available")
        
        # Load .env file manually
        load_dotenv()
        
        # Check again after loading
        pexels_base_url_after = os.getenv('PEXELS_BASE_URL')
        pexels_secret_key_after = os.getenv('PEXELS_SECRET_KEY')
        
        print(f"After load_dotenv():")
        print(f"PEXELS_BASE_URL: {pexels_base_url_after if pexels_base_url_after else '❌ Still not set'}")
        print(f"PEXELS_SECRET_KEY: {pexels_secret_key_after[:10] + '...' if pexels_secret_key_after else '❌ Still not set'}")
        
    except ImportError:
        print("❌ python-dotenv is not available")
    except Exception as e:
        print(f"❌ Error loading .env: {e}")
    
    # Check all environment variables that start with PEXELS
    print("\n=== All PEXELS Environment Variables ===")
    pexels_vars = {k: v for k, v in os.environ.items() if k.startswith('PEXELS')}
    if pexels_vars:
        for key, value in pexels_vars.items():
            if 'SECRET' in key or 'KEY' in key:
                print(f"{key}: {value[:10]}..." if len(value) > 10 else f"{key}: {value}")
            else:
                print(f"{key}: {value}")
    else:
        print("No PEXELS environment variables found")

if __name__ == "__main__":
    main()
