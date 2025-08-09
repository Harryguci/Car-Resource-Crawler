# src/backgroundworker/car_crawler.py
# Define a background worker for crawling images of cars

import asyncio
import httpx
import aiofiles
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import time
from urllib.parse import urljoin, urlparse

from src.config.settings import settings
from src.utils.env_utils import get_pexels_config

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

class PexelsCarCrawler:
    """Background worker for crawling car images from Pexels API"""
    
    def __init__(self):
        self.config = get_pexels_config()
        self.base_url = self.config.get("pexels_base_url", "https://www.pexels.com/en-us/api/v3")
        self.secret_key = self.config.get("pexels_secret_key")
        self.request_frequency = self.config.get("request_frequency", 60)  # seconds between requests. Default is 60 seconds.
        self.resource_dir = Path(self.config.get("resource_dir", "blob/pexels"))
        
        # Ensure resource directory exists
        self.resource_dir.mkdir(parents=True, exist_ok=True)
        
        # Client for HTTP requests
        self.client: Optional[httpx.AsyncClient] = None
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_downloads": 0,
            "failed_downloads": 0,
            "errors": 0,
            "start_time": None,
            "last_request_time": None
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            headers={
                "accept": "*/*",
                "accept-language": "en-US,en;q=0.9",
                "content-type": "application/json",
                "secret-key": self.secret_key,
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                "x-client-type": "react"
            },
            timeout=30.0
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    def _validate_config(self) -> bool:
        """Validate that required configuration is present"""
        if not self.secret_key:
            logger.error("Pexels secret key is not configured")
            return False
        
        if not self.base_url:
            logger.error("Pexels base URL is not configured")
            return False
        
        return True
    
    async def _make_request(self, url: str, params: Dict[str, Any] = None) -> Optional[Dict]:
        """Make HTTP request to Pexels API with rate limiting"""
        if not self.client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        # Rate limiting
        if self.stats["last_request_time"]:
            time_since_last = time.time() - self.stats["last_request_time"]
            if time_since_last < self.request_frequency:
                await asyncio.sleep(self.request_frequency - time_since_last)
        
        try:
            self.stats["total_requests"] += 1
            self.stats["last_request_time"] = time.time()
            
            response = await self.client.get(url, params=params)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Rate limit exceeded. Waiting 60 seconds...")
                await asyncio.sleep(60)
                return await self._make_request(url, params)
            else:
                logger.error(f"API request failed with status {response.status_code}: {response.text}")
                self.stats["errors"] += 1
                return None
                
        except Exception as e:
            logger.error(f"Request error: {str(e)}")
            self.stats["errors"] += 1
            return None
    
    async def search_cars(self, query: str = "car", page: int = 1, per_page: int = 24) -> Optional[Dict]:
        """Search for car images on Pexels"""
        url = f"{self.base_url}/search/photos"
        params = {
            "query": query,
            "page": page,
            "per_page": per_page,
            "orientation": "all",
            "size": "all",
            "color": "all",
            "sort": "popular",
            "seo_tags": "true"
        }
        
        logger.info(f"Searching for cars with query: {query}, page: {page}")
        return await self._make_request(url, params)
    
    async def download_image(self, image_url: str, filename: str) -> bool:
        """Download an image from URL and save to local storage"""
        try:
            if not self.client:
                raise RuntimeError("Client not initialized")
            
            response = await self.client.get(image_url)
            
            if response.status_code == 200:
                file_path = self.resource_dir / filename
                
                # Ensure directory exists
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(response.content)
                
                logger.info(f"Downloaded image: {filename}")
                self.stats["successful_downloads"] += 1
                return True
            else:
                logger.error(f"Failed to download image {image_url}: HTTP {response.status_code}")
                self.stats["failed_downloads"] += 1
                return False
                
        except Exception as e:
            logger.error(f"Error downloading image {image_url}: {str(e)}")
            self.stats["failed_downloads"] += 1
            return False
    
    def _generate_filename(self, photo_data: Dict, index: int) -> str:
        """Generate a unique filename for the image"""
        photographer = photo_data.get("photographer", "unknown")
        photo_id = photo_data.get("id", f"img_{index}")
        extension = "jpg"  # Default extension
        
        # Clean photographer name for filename
        photographer_clean = "".join(c for c in photographer if c.isalnum() or c in (' ', '-', '_')).rstrip()
        photographer_clean = photographer_clean.replace(' ', '_')
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{photographer_clean}_{photo_id}_{timestamp}.{extension}"
    
    async def crawl_car_images(self, 
                              search_queries: List[str] = None,
                              max_pages: int = 5,
                              images_per_page: int = 24) -> Dict[str, Any]:
        """Main crawling function"""
        if not self._validate_config():
            return {"error": "Invalid configuration"}
        
        if search_queries is None:
            search_queries = ["car", "automobile", "vehicle", "sports car", "luxury car"]
        
        self.stats["start_time"] = time.time()
        logger.info(f"Starting car image crawling with queries: {search_queries}")
        
        total_downloaded = 0
        
        for query in search_queries:
            logger.info(f"Processing query: {query}")
            
            for page in range(1, max_pages + 1):
                try:
                    # Search for images
                    search_result = await self.search_cars(query, page, images_per_page)
                    
                    if not search_result:
                        logger.warning(f"No results for query '{query}' on page {page}")
                        continue
                    
                    photos = search_result.get("photos", [])
                    if not photos:
                        logger.info(f"No more photos for query '{query}' on page {page}")
                        break
                    
                    logger.info(f"Found {len(photos)} photos for query '{query}' on page {page}")
                    
                    # Download each image
                    for index, photo in enumerate(photos):
                        try:
                            # Get the largest available image URL
                            src = photo.get("src", {})
                            image_url = src.get("large2x") or src.get("large") or src.get("medium")
                            
                            if not image_url:
                                logger.warning(f"No image URL found for photo {photo.get('id')}")
                                continue
                            
                            # Generate filename
                            filename = self._generate_filename(photo, index)
                            
                            # Download image
                            success = await self.download_image(image_url, filename)

                            # TODO: Make a POST request to the API to save the image to the database. Avoid duplicates resource.

                            if success:
                                total_downloaded += 1
                            
                            # Small delay between downloads
                            await asyncio.sleep(0.5)
                            
                        except Exception as e:
                            logger.error(f"Error processing photo {photo.get('id')}: {str(e)}")
                            self.stats["errors"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing page {page} for query '{query}': {str(e)}")
                    self.stats["errors"] += 1
                    continue
        
        # Calculate final statistics
        duration = time.time() - self.stats["start_time"]
        self.stats["duration"] = duration
        self.stats["total_downloaded"] = total_downloaded
        
        logger.info(f"Crawling completed. Downloaded {total_downloaded} images in {duration:.2f} seconds")
        logger.info(f"Final stats: {self.stats}")
        
        return {
            "success": True,
            "total_downloaded": total_downloaded,
            "duration": duration,
            "stats": self.stats
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current crawling statistics"""
        return self.stats.copy()

async def run_car_crawler(search_queries: List[str] = None, 
                         max_pages: int = 5, 
                         images_per_page: int = 24) -> Dict[str, Any]:
    """Convenience function to run the car crawler"""
    async with PexelsCarCrawler() as crawler:
        return await crawler.crawl_car_images(search_queries, max_pages, images_per_page)

# Example usage and testing
if __name__ == "__main__":
    async def main():
        # Example usage
        queries = ["car", "sports car", "luxury car"]
        result = await run_car_crawler(
            search_queries=queries,
            max_pages=2,
            images_per_page=12
        )
        print(f"Crawling result: {result}")
    
    # Run the example
    asyncio.run(main())