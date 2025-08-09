#!/usr/bin/env python3
"""
Comprehensive debug script for Pexels API issues
"""

import asyncio
import httpx
import logging
import os
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_basic_request():
    """Test basic request without any special headers"""
    logger.info("=== Testing Basic Request ===")
    
    url = "https://www.pexels.com/en-us/api/v3/search/photos"
    params = {
        "query": "car",
        "page": 1,
        "per_page": 5
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            logger.info(f"Basic request status: {response.status_code}")
            logger.info(f"Response text: {response.text[:200]}...")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Basic request error: {e}")
            return False

async def test_with_headers():
    """Test with browser-like headers"""
    logger.info("=== Testing with Browser Headers ===")
    
    url = "https://www.pexels.com/en-us/api/v3/search/photos"
    params = {
        "query": "car",
        "page": 1,
        "per_page": 5
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
    
    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            logger.info(f"Headers request status: {response.status_code}")
            logger.info(f"Response text: {response.text[:200]}...")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Headers request error: {e}")
            return False

async def test_with_cookies():
    """Test with cookies from sample API"""
    logger.info("=== Testing with Cookies ===")
    
    url = "https://www.pexels.com/en-us/api/v3/search/photos"
    params = {
        "query": "car",
        "page": 1,
        "per_page": 5
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
    
    cookies = {
        "active_experiment": "none",
        "country-code-v2": "VN",
        "OptanonConsent": "isGpcEnabled=0&datestamp=Sat+Aug+09+2025+14%3A26%3A01+GMT%2B0700+(Indochina+Time)&version=202301.1.0&isIABGlobal=false&hosts=&landingPath=https%3A%2F%2Fwww.pexels.com%2F&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1"
    }
    
    async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            logger.info(f"Cookies request status: {response.status_code}")
            logger.info(f"Response text: {response.text[:200]}...")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Cookies request error: {e}")
            return False

async def test_with_secret_key():
    """Test with secret key from environment"""
    logger.info("=== Testing with Secret Key ===")
    
    # Get secret key from environment
    secret_key = os.getenv('PEXELS_SECRET_KEY')
    if not secret_key:
        logger.warning("No PEXELS_SECRET_KEY found in environment")
        return False
    
    url = "https://www.pexels.com/en-us/api/v3/search/photos"
    params = {
        "query": "car",
        "page": 1,
        "per_page": 5
    }
    
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9,vi;q=0.8",
        "content-type": "application/json",
        "secret-key": secret_key,
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
    
    async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=30.0) as client:
        try:
            response = await client.get(url, params=params)
            logger.info(f"Secret key request status: {response.status_code}")
            logger.info(f"Response text: {response.text[:200]}...")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Secret key request error: {e}")
            return False

async def test_different_urls():
    """Test different possible API URLs"""
    logger.info("=== Testing Different URLs ===")
    
    urls_to_test = [
        "https://www.pexels.com/en-us/api/v3/search/photos",
        "https://www.pexels.com/en-us/api/v3/search",
        "https://api.pexels.com/v1/search",
        "https://www.pexels.com/api/v3/search/photos"
    ]
    
    params = {
        "query": "car",
        "page": 1,
        "per_page": 5
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
    
    cookies = {
        "active_experiment": "none",
        "country-code-v2": "VN",
        "OptanonConsent": "isGpcEnabled=0&datestamp=Sat+Aug+09+2025+14%3A26%3A01+GMT%2B0700+(Indochina+Time)&version=202301.1.0&isIABGlobal=false&hosts=&landingPath=https%3A%2F%2Fwww.pexels.com%2F&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1"
    }
    
    for url in urls_to_test:
        logger.info(f"Testing URL: {url}")
        async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=30.0) as client:
            try:
                response = await client.get(url, params=params)
                logger.info(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    logger.info(f"  ✅ Success with URL: {url}")
                    return url
                else:
                    logger.info(f"  ❌ Failed with status {response.status_code}")
            except Exception as e:
                logger.error(f"  ❌ Error: {e}")
    
    return None

async def main():
    """Run all tests"""
    logger.info("Starting Pexels API debugging...")
    
    # Test 1: Basic request
    basic_success = await test_basic_request()
    
    # Test 2: With headers
    headers_success = await test_with_headers()
    
    # Test 3: With cookies
    cookies_success = await test_with_cookies()
    
    # Test 4: With secret key
    secret_success = await test_with_secret_key()
    
    # Test 5: Different URLs
    working_url = await test_different_urls()
    
    # Summary
    logger.info("\n=== SUMMARY ===")
    logger.info(f"Basic request: {'✅' if basic_success else '❌'}")
    logger.info(f"With headers: {'✅' if headers_success else '❌'}")
    logger.info(f"With cookies: {'✅' if cookies_success else '❌'}")
    logger.info(f"With secret key: {'✅' if secret_success else '❌'}")
    logger.info(f"Working URL found: {working_url if working_url else '❌ None'}")

if __name__ == "__main__":
    asyncio.run(main())
