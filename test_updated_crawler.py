#!/usr/bin/env python3
"""
Test the updated crawler with the new API structure
"""

import asyncio
import logging
from src.backgroundworker.car_crawler import PexelsCarCrawler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_updated_crawler():
    """Test the updated crawler"""
    logger.info("=== Testing Updated Pexels Car Crawler ===")
    
    try:
        async with PexelsCarCrawler() as crawler:
            # Test a simple search
            result = await crawler.search_cars("car", 1, 3)
            
            if result:
                logger.info("✅ Search successful!")
                
                # Check the structure
                photos = result.get("data", [])
                logger.info(f"Found {len(photos)} photos")
                
                if photos:
                    first_photo = photos[0]
                    logger.info(f"First photo ID: {first_photo.get('id')}")
                    
                    # Check attributes
                    attributes = first_photo.get("attributes", {})
                    logger.info(f"Photo title: {attributes.get('title', 'No title')}")
                    logger.info(f"Photo description: {attributes.get('description', 'No description')[:100]}...")
                    
                    # Check user info
                    user = attributes.get("user", {})
                    if user:
                        logger.info(f"Photographer: {user.get('first_name', '')} {user.get('last_name', '')}")
                    
                    # Check image URLs
                    image_data = attributes.get("image", {})
                    if isinstance(image_data, dict):
                        logger.info(f"Image URLs available:")
                        logger.info(f"  - Small: {image_data.get('small', 'Not available')}")
                        logger.info(f"  - Medium: {image_data.get('medium', 'Not available')}")
                        logger.info(f"  - Large: {image_data.get('large', 'Not available')}")
                        logger.info(f"  - Download: {image_data.get('download_link', 'Not available')}")
                    else:
                        logger.info(f"Image URL: {image_data}")
                
                return True
            else:
                logger.error("❌ Search failed!")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error testing crawler: {str(e)}")
        return False

async def test_small_crawl():
    """Test a small crawl operation"""
    logger.info("=== Testing Small Crawl Operation ===")
    
    try:
        async with PexelsCarCrawler() as crawler:
            # Test with just one query and one page
            result = await crawler.crawl_car_images(
                search_queries=["car"],
                max_pages=1,
                images_per_page=2
            )
            
            logger.info(f"Crawl result: {result}")
            
            if result.get("success"):
                logger.info("✅ Crawl successful!")
                logger.info(f"Total saved: {result.get('total_saved', 0)}")
                logger.info(f"Total downloaded: {result.get('total_downloaded', 0)}")
                return True
            else:
                logger.error("❌ Crawl failed!")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error in crawl test: {str(e)}")
        return False

async def main():
    """Main test function"""
    logger.info("Starting updated crawler tests...")
    
    # Test 1: Basic search functionality
    search_success = await test_updated_crawler()
    
    # Test 2: Small crawl operation
    if search_success:
        crawl_success = await test_small_crawl()
    else:
        crawl_success = False
    
    # Summary
    logger.info("\n=== SUMMARY ===")
    logger.info(f"Search functionality: {'✅' if search_success else '❌'}")
    logger.info(f"Crawl functionality: {'✅' if crawl_success else '❌'}")
    
    if search_success and crawl_success:
        logger.info("🎉 All tests passed! The crawler is working correctly.")
    else:
        logger.info("❌ Some tests failed. Check the logs for details.")

if __name__ == "__main__":
    asyncio.run(main())
