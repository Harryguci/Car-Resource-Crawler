#!/usr/bin/env python3
"""
Fixed debug script for Pexels API issues - uses proper settings loading
"""

import asyncio
import httpx
import logging
import os
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_with_proper_settings():
    """Test using the proper settings module"""
    logger.info("=== Testing with Proper Settings ===")
    
    try:
        # Import settings after ensuring environment is loaded
        from src.config.settings import settings
        from src.utils.env_utils import get_pexels_config
        
        # Get config from the same source as the crawler
        config = get_pexels_config()
        base_url = config.get("pexels_base_url", "https://www.pexels.com/en-us/api/v3")
        secret_key = config.get("pexels_secret_key")
        
        logger.info(f"Base URL from settings: {base_url}")
        logger.info(f"Secret key from settings: {secret_key[:10] + '...' if secret_key else 'Not set'}")
        
        # Remove any trailing /search/photos from base_url if present
        if base_url.endswith("/search/photos"):
            base_url = base_url.replace("/search/photos", "")
        
        url = f"{base_url}/search/photos"
        params = {
            "query": "car",
            "page": 1,
            "per_page": 5,
            "orientation": "all",
            "size": "all",
            "color": "all",
            "sort": "popular",
            "seo_tags": "true"
        }
        
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,vi;q=0.8",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
            "x-client-type": "react",
            "referer": "https://www.pexels.com/search/car/",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        }
        
        # Add secret key if available
        if secret_key:
            headers["secret-key"] = secret_key
            logger.info("✅ Secret key added to headers")
        else:
            logger.warning("❌ No secret key available")
        
        cookies = {
            "active_experiment": "none",
            "country-code-v2": "VN",
            "OptanonConsent": "isGpcEnabled=0&datestamp=Sat+Aug+09+2025+14%3A26%3A01+GMT%2B0700+(Indochina+Time)&version=202301.1.0&isIABGlobal=false&hosts=&landingPath=https%3A%2F%2Fwww.pexels.com%2F&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1"
        }
        
        logger.info(f"Making request to: {url}")
        logger.info(f"With params: {params}")
        
        async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(url, params=params)
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response headers: {dict(response.headers)}")
                logger.info(f"Response text: {response.text[:500]}...")
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info("✅ Request successful!")
                    logger.info(f"Found {len(data.get('photos', []))} photos")
                    return True
                else:
                    logger.error(f"❌ Request failed with status {response.status_code}")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Request error: {str(e)}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error loading settings: {str(e)}")
        return False

async def test_alternative_auth_methods():
    """Test alternative authentication methods"""
    logger.info("=== Testing Alternative Auth Methods ===")
    
    try:
        from src.utils.env_utils import get_pexels_config
        config = get_pexels_config()
        secret_key = config.get("pexels_secret_key")
        
        if not secret_key:
            logger.warning("No secret key available for testing")
            return False
        
        # Test different header names for the secret key
        auth_methods = [
            {"secret-key": secret_key},
            {"Authorization": f"Bearer {secret_key}"},
            {"X-API-Key": secret_key},
            {"api-key": secret_key},
            {"key": secret_key}
        ]
        
        url = "https://www.pexels.com/en-us/api/v3/search/photos"
        params = {
            "query": "car",
            "page": 1,
            "per_page": 5
        }
        
        base_headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,vi;q=0.8",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
            "x-client-type": "react",
            "referer": "https://www.pexels.com/search/car/",
            "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        }
        
        cookies = {
            "active_experiment": "none",
            "country-code-v2": "VN",
            "OptanonConsent": "isGpcEnabled=0&datestamp=Sat+Aug+09+2025+14%3A26%3A01+GMT%2B0700+(Indochina+Time)&version=202301.1.0&isIABGlobal=false&hosts=&landingPath=https%3A%2F%2Fwww.pexels.com%2F&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1"
        }
        
        for i, auth_headers in enumerate(auth_methods, 1):
            logger.info(f"Testing auth method {i}: {list(auth_headers.keys())}")
            
            headers = {**base_headers, **auth_headers}
            
            async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=30.0, follow_redirects=True) as client:
                try:
                    response = await client.get(url, params=params)
                    logger.info(f"  Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        logger.info(f"  ✅ Success with auth method {i}: {list(auth_headers.keys())}")
                        return True
                    elif response.status_code == 401:
                        logger.info(f"  ❌ Unauthorized with auth method {i}")
                    else:
                        logger.info(f"  ❌ Failed with status {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"  ❌ Error: {str(e)}")
        
        return False
        
    except Exception as e:
        logger.error(f"❌ Error in alternative auth test: {str(e)}")
        return False

async def main():
    """Run all tests"""
    logger.info("Starting Pexels API debugging with proper settings...")
    
    # Test 1: With proper settings
    settings_success = await test_with_proper_settings()
    
    # Test 2: Alternative auth methods
    if not settings_success:
        auth_success = await test_alternative_auth_methods()
    else:
        auth_success = True
    
    # Summary
    logger.info("\n=== SUMMARY ===")
    logger.info(f"With proper settings: {'✅' if settings_success else '❌'}")
    logger.info(f"Alternative auth methods: {'✅' if auth_success else '❌'}")
    
    if settings_success or auth_success:
        logger.info("🎉 API connection successful!")
    else:
        logger.info("❌ All authentication methods failed")
        logger.info("💡 Possible solutions:")
        logger.info("   1. Check if the secret key is valid")
        logger.info("   2. Verify the API endpoint is correct")
        logger.info("   3. Check if the API requires different authentication")

if __name__ == "__main__":
    asyncio.run(main())
