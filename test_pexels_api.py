#!/usr/bin/env python3
"""
Test script for Pexels API connection
"""

import asyncio
import httpx
import logging
from src.backgroundworker.car_crawler import PexelsCarCrawler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_pexels_api():
    """Test the Pexels API connection"""
    logger.info("Testing Pexels API connection...")
    
    async with PexelsCarCrawler() as crawler:
        # Test a simple search
        result = await crawler.search_cars("car", 1, 5)
        
        if result:
            logger.info("✅ API connection successful!")
            logger.info(f"Found {len(result.get('photos', []))} photos")
            
            # Show first photo details if available
            photos = result.get('photos', [])
            if photos:
                first_photo = photos[0]
                logger.info(f"First photo ID: {first_photo.get('id')}")
                logger.info(f"Photographer: {first_photo.get('photographer', {}).get('name', 'Unknown')}")
                logger.info(f"Image URL: {first_photo.get('src', {}).get('large2x', 'No URL')}")
        else:
            logger.error("❌ API connection failed!")

async def test_direct_request():
    """Test direct HTTP request to understand the issue better"""
    logger.info("Testing direct HTTP request...")
    
    # Use the same configuration as the crawler
    from src.utils.env_utils import get_pexels_config
    config = get_pexels_config()
    
    base_url = config.get("pexels_base_url", "https://www.pexels.com/en-us/api/v3")
    secret_key = config.get("pexels_secret_key")
    
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
    
    cookies = {
        "active_experiment": "none",
        "country-code-v2": "VN",
        "OptanonConsent": "isGpcEnabled=0&datestamp=Sat+Aug+09+2025+14%3A26%3A01+GMT%2B0700+(Indochina+Time)&version=202301.1.0&isIABGlobal=false&hosts=&landingPath=https%3A%2F%2Fwww.pexels.com%2F&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1"
    }
    
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9,vi;q=0.8",
        "content-type": "application/json",
        "secret-key": secret_key,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
        "x-client-type": "react",
        "priority": "u=1, i",
        "referer": "https://www.pexels.com/search/car/",
        "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Microsoft Edge";v="138"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin"
    }
    
    logger.info(f"Making request to: {url}")
    logger.info(f"With params: {params}")
    logger.info(f"With secret key: {secret_key[:10]}..." if secret_key else "No secret key")
    
    async with httpx.AsyncClient(cookies=cookies, headers=headers, timeout=30.0, follow_redirects=True) as client:
        try:
            response = await client.get(url, params=params)
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info("✅ Direct request successful!")
                logger.info(f"Found {len(data.get('photos', []))} photos")
                return data
            else:
                logger.error(f"❌ Direct request failed with status {response.status_code}")
                logger.error(f"Response text: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Direct request error: {str(e)}")
            return None

async def main():
    """Main test function"""
    logger.info("Starting Pexels API tests...")
    
    # Test 1: Direct request
    logger.info("\n" + "="*50)
    logger.info("TEST 1: Direct HTTP Request")
    logger.info("="*50)
    await test_direct_request()
    
    # Test 2: Using crawler
    logger.info("\n" + "="*50)
    logger.info("TEST 2: Using PexelsCarCrawler")
    logger.info("="*50)
    await test_pexels_api()
    
    logger.info("\nTests completed!")

if __name__ == "__main__":
    asyncio.run(main())
