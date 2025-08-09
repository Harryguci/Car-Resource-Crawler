#!/usr/bin/env python3
"""
Examine the actual API response structure
"""

import asyncio
import httpx
import json
import logging
from src.utils.env_utils import get_pexels_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def examine_api_response():
    """Examine the actual API response structure"""
    logger.info("=== Examining API Response Structure ===")
    
    try:
        # Get config
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
        
        # Add secret key
        if secret_key:
            headers["secret-key"] = secret_key
        
        cookies = {
            "active_experiment": "none",
            "country-code-v2": "VN",
            "OptanonConsent": "isGpcEnabled=0&datestamp=Sat+Aug+09+2025+14%3A26%3A01+GMT%2B0700+(Indochina+Time)&version=202301.1.0&isIABGlobal=false&hosts=&landingPath=https%3A%2F%2Fwww.pexels.com%2F&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1"
        }
        
        async with httpx.AsyncClient(headers=headers, cookies=cookies, timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                logger.info("✅ API Response Structure Analysis:")
                logger.info("=" * 50)
                
                # Print the top-level keys
                logger.info(f"Top-level keys: {list(data.keys())}")
                
                # Examine the structure
                for key, value in data.items():
                    if isinstance(value, list):
                        logger.info(f"Key '{key}' is a list with {len(value)} items")
                        if value:
                            logger.info(f"  First item keys: {list(value[0].keys()) if isinstance(value[0], dict) else 'Not a dict'}")
                    elif isinstance(value, dict):
                        logger.info(f"Key '{key}' is a dict with keys: {list(value.keys())}")
                    else:
                        logger.info(f"Key '{key}' is {type(value).__name__}: {value}")
                
                # Look for photos data
                if 'data' in data:
                    logger.info("\n📸 Photos Data Structure:")
                    photos_data = data['data']
                    if photos_data:
                        first_photo = photos_data[0]
                        logger.info(f"First photo structure:")
                        logger.info(f"  Keys: {list(first_photo.keys())}")
                        
                        if 'attributes' in first_photo:
                            attrs = first_photo['attributes']
                            logger.info(f"  Attributes keys: {list(attrs.keys())}")
                            
                            # Look for image URLs
                            for attr_key, attr_value in attrs.items():
                                if 'url' in attr_key.lower() or 'src' in attr_key.lower():
                                    logger.info(f"    {attr_key}: {attr_value}")
                
                # Save full response to file for detailed analysis
                with open('api_response_example.json', 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                logger.info("\n💾 Full response saved to 'api_response_example.json'")
                
                return data
            else:
                logger.error(f"❌ API request failed with status {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return None

async def main():
    """Main function"""
    await examine_api_response()

if __name__ == "__main__":
    asyncio.run(main())
