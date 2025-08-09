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
from src.database.connection import SessionLocal
from src.services.image_resource_service import ImageResourceService
from src.models.image_resource import ImageResourceCreate

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)

class PexelsCarCrawler:
    """Background worker for crawling car images from Pexels API"""
    
    def __init__(self):
        self.config = get_pexels_config()
        # Fix base URL - should be just the base, not the full endpoint
        self.base_url = self.config.get("pexels_base_url", "https://www.pexels.com/en-us/api/v3")
        # Remove any trailing /search/photos from base_url if present
        if self.base_url.endswith("/search/photos"):
            self.base_url = self.base_url.replace("/search/photos", "")
        self.secret_key = self.config.get("pexels_secret_key")
        self.request_frequency = self.config.get("request_frequency", 60)  # seconds between requests. Default is 60 seconds.
        self.resource_dir = Path(self.config.get("resource_dir", "blob/pexels"))
        
        # Ensure resource directory exists
        self.resource_dir.mkdir(parents=True, exist_ok=True)
        
        # Client for HTTP requests
        self.client: Optional[httpx.AsyncClient] = None
        
        # Database session and service
        self.db_session: Optional[SessionLocal] = None
        self.image_service: Optional[ImageResourceService] = None
        
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
        # Set up cookies similar to the sample API
        cookies = {
            "active_experiment": "none",
            "country-code-v2": "VN",
            "OptanonConsent": "isGpcEnabled=0&datestamp=Sat+Aug+09+2025+14%3A26%3A01+GMT%2B0700+(Indochina+Time)&version=202301.1.0&isIABGlobal=false&hosts=&landingPath=https%3A%2F%2Fwww.pexels.com%2F&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1"
        }
        
        # Try different header configurations
        base_headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,vi;q=0.8",
            "content-type": "application/json",
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
        
        # Add secret key if available
        if self.secret_key:
            base_headers["secret-key"] = self.secret_key
        
        self.client = httpx.AsyncClient(
            headers=base_headers,
            cookies=cookies,
            timeout=30.0,
            follow_redirects=True  # Enable automatic redirect following
        )
        
        # Initialize database session and service
        self.db_session = SessionLocal()
        self.image_service = ImageResourceService(self.db_session)
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
        
        # Close database session
        if self.db_session:
            self.db_session.close()
    
    def _validate_config(self) -> bool:
        """Validate that required configuration is present"""
        if not self.secret_key:
            logger.error("Pexels secret key is not configured")
            return False
        
        if not self.base_url:
            logger.error("Pexels base URL is not configured")
            return False
        
        return True
    
    def _check_image_exists(self, image_url: str) -> bool:
        """Check if image already exists in database by URL"""
        try:
            existing_image = self.image_service.get_image_resource_by_url(image_url)
            return existing_image is not None
        except Exception as e:
            logger.error(f"Error checking if image exists: {e}")
            return False
    
    def _save_image_record(self, photo_data: Dict, image_url: str, filename: str, search_query: str) -> Optional[str]:
        """Save image resource record to database"""
        try:
            # Extract photo information from new API structure
            attributes = photo_data.get("attributes", {})
            
            # Get photographer information
            user = attributes.get("user", {})
            photographer_name = None
            photographer_url = None
            if user:
                first_name = user.get("first_name", "")
                last_name = user.get("last_name", "")
                photographer_name = f"{first_name} {last_name}".strip()
                photographer_url = f"https://www.pexels.com/@{user.get('username', '')}"
            
            # Get image dimensions if available
            width = attributes.get("width")
            height = attributes.get("height")
            
            # Get file format from URL
            format_ext = Path(urlparse(image_url).path).suffix.lstrip('.')
            
            # Create image resource data
            image_data = ImageResourceCreate(
                url=image_url,
                filename=filename,
                file_path=str(self.resource_dir / filename),
                source="pexels",
                search_query=search_query,
                description=attributes.get("description", ""),
                photographer=photographer_name,
                photographer_url=photographer_url,
                width=width,
                height=height,
                format=format_ext if format_ext else None
            )
            
            # Save to database
            saved_image = self.image_service.create_image_resource(image_data)
            logger.info(f"Saved image record: {saved_image.id} for URL: {image_url}")
            return saved_image.id
            
        except Exception as e:
            logger.error(f"Error saving image record: {e}")
            return None
    
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
            
            # Log the full URL being requested for debugging
            full_url = f"{url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}" if params else url
            logger.info(f"Making request to: {full_url}")
            
            response = await self.client.get(url, params=params)
            
            # Log response details for debugging
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Rate limit exceeded. Waiting 60 seconds...")
                await asyncio.sleep(60)
                return await self._make_request(url, params)
            elif response.status_code == 307:
                logger.error(f"Redirect error (307). Response text: {response.text}")
                logger.error(f"Response headers: {dict(response.headers)}")
                
                # Try to follow the redirect manually
                location = response.headers.get('location')
                if location:
                    logger.info(f"Following redirect to: {location}")
                    return await self._make_request(location, params)
                
                self.stats["errors"] += 1
                return None
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
        # Try different API endpoint structures
        possible_urls = [
            f"{self.base_url}/search/photos",
            f"{self.base_url}/search",
            "https://www.pexels.com/en-us/api/v3/search/photos"
        ]
        
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
        
        # Try each possible URL
        for url in possible_urls:
            logger.info(f"Trying URL: {url}")
            result = await self._make_request(url, params)
            if result:
                logger.info(f"Success with URL: {url}")
                return result
        
        logger.error("All URL attempts failed")
        return None
    
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
        # Get photographer name from new API structure
        attributes = photo_data.get("attributes", {})
        user = attributes.get("user", {})
        
        if user:
            first_name = user.get("first_name", "")
            last_name = user.get("last_name", "")
            photographer = f"{first_name} {last_name}".strip()
        else:
            photographer = "unknown"
        
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
        total_saved = 0
        
        for query in search_queries:
            logger.info(f"Processing query: {query}")
            
            for page in range(1, max_pages + 1):
                try:
                    # Search for images
                    search_result = await self.search_cars(query, page, images_per_page)
                    
                    if not search_result:
                        logger.warning(f"No results for query '{query}' on page {page}")
                        continue
                    
                    # The new API structure has photos in data array
                    photos = search_result.get("data", [])
                    if not photos:
                        logger.info(f"No more photos for query '{query}' on page {page}")
                        break
                    
                    logger.info(f"Found {len(photos)} photos for query '{query}' on page {page}")
                    
                    # Download each image
                    for index, photo in enumerate(photos):
                        try:
                            # Get photo attributes
                            attributes = photo.get("attributes", {})
                            
                            # Get the largest available image URL from the new structure
                            image_data = attributes.get("image", {})
                            if isinstance(image_data, dict):
                                # New API structure with multiple sizes
                                image_url = (image_data.get("download_link") or 
                                           image_data.get("large") or 
                                           image_data.get("medium") or 
                                           image_data.get("small"))
                            else:
                                # Fallback for string URL
                                image_url = image_data
                            
                            if not image_url:
                                logger.warning(f"No image URL found for photo {photo.get('id')}")
                                continue
                            
                            # Check if image already exists in database
                            if self._check_image_exists(image_url):
                                logger.info(f"Image already exists in database: {image_url}")
                                continue
                            
                            # Generate filename
                            filename = self._generate_filename(photo, index)
                            
                            # Save image record to database first
                            image_id = self._save_image_record(photo, image_url, filename, query)
                            if image_id:
                                total_saved += 1
                            
                            # Download image
                            success = await self.download_image(image_url, filename)

                            # Update download status in database
                            if image_id:
                                if success:
                                    self.image_service.update_download_status(image_id, "completed")
                                    total_downloaded += 1
                                else:
                                    self.image_service.update_download_status(image_id, "failed", "Download failed")
                            
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
        self.stats["total_saved"] = total_saved
        
        logger.info(f"Crawling completed. Saved {total_saved} records, downloaded {total_downloaded} images in {duration:.2f} seconds")
        logger.info(f"Final stats: {self.stats}")
        
        return {
            "success": True,
            "total_saved": total_saved,
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