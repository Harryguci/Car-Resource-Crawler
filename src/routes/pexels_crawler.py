from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from src.backgroundworker.car_crawler import PexelsCarCrawler
from src.utils.env_utils import get_pexels_config
from src.config.logging_config import get_logger
import asyncio
from typing import Optional, List
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter()

# Global crawler instance for monitoring
crawler_instance: Optional[PexelsCarCrawler] = None
crawler_task: Optional[asyncio.Task] = None
crawler_status = {
    "is_running": False,
    "start_time": None,
    "last_update": None,
    "current_query": None,
    "progress": {
        "current_page": 0,
        "total_pages": 0,
        "images_downloaded": 0
    }
}

@router.post("/crawler/start")
async def start_car_crawler(
    background_tasks: BackgroundTasks,
    search_queries: Optional[list[str]] = None,
    max_pages: int = 5,
    images_per_page: int = 24
):
    """Start the car image crawler in the background"""
    global crawler_instance, crawler_task, crawler_status
    
    if crawler_status["is_running"]:
        raise HTTPException(status_code=400, detail="Crawler is already running")
    
    # Validate Pexels configuration
    pexels_config = get_pexels_config()
    if not pexels_config.get("pexels_secret_key"):
        raise HTTPException(
            status_code=400, 
            detail="Pexels secret key not configured. Please set PEXELS_SECRET_KEY environment variable."
        )
    
    # Set default queries if none provided
    if search_queries is None:
        search_queries = ["car", "automobile", "vehicle", "sports car", "luxury car"]
    
    # Update crawler status
    crawler_status.update({
        "is_running": True,
        "start_time": datetime.now().isoformat(),
        "last_update": datetime.now().isoformat(),
        "current_query": search_queries[0] if search_queries else None,
        "progress": {
            "current_page": 0,
            "total_pages": max_pages,
            "images_downloaded": 0
        }
    })
    
    # Start crawler in background
    async def run_crawler():
        global crawler_instance, crawler_status
        try:
            async with PexelsCarCrawler() as crawler:
                crawler_instance = crawler
                result = await crawler.crawl_car_images(
                    search_queries=search_queries,
                    max_pages=max_pages,
                    images_per_page=images_per_page
                )
                
                # Update final status
                crawler_status.update({
                    "is_running": False,
                    "last_update": datetime.now().isoformat(),
                    "final_result": result
                })
                
                logger.info(f"Crawler completed: {result}")
                
        except Exception as e:
            logger.error(f"Crawler error: {str(e)}")
            crawler_status.update({
                "is_running": False,
                "last_update": datetime.now().isoformat(),
                "error": str(e)
            })
        finally:
            crawler_instance = None
    
    # Start the background task
    crawler_task = asyncio.create_task(run_crawler())
    
    return {
        "message": "Car crawler started successfully",
        "search_queries": search_queries,
        "max_pages": max_pages,
        "images_per_page": images_per_page,
        "status": "running"
    }

@router.get("/crawler/status")
async def get_crawler_status():
    """Get the current status of the car crawler"""
    global crawler_instance, crawler_status
    
    # Get current stats if crawler is running
    current_stats = None
    if crawler_instance and crawler_status["is_running"]:
        current_stats = crawler_instance.get_stats()
        # Update progress based on current stats
        if current_stats:
            crawler_status["progress"]["images_downloaded"] = current_stats.get("successful_downloads", 0)
            crawler_status["last_update"] = datetime.now().isoformat()
    
    return {
        "crawler_status": crawler_status,
        "current_stats": current_stats,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/crawler/stop")
async def stop_crawler():
    """Stop the running car crawler"""
    global crawler_task, crawler_status
    
    if not crawler_status["is_running"]:
        raise HTTPException(status_code=400, detail="No crawler is currently running")
    
    # Cancel the background task
    if crawler_task and not crawler_task.done():
        crawler_task.cancel()
        try:
            await crawler_task
        except asyncio.CancelledError:
            pass
    
    crawler_status.update({
        "is_running": False,
        "last_update": datetime.now().isoformat(),
        "status": "stopped"
    })
    
    return {
        "message": "Crawler stopped successfully",
        "status": "stopped"
    }

@router.get("/crawler/test")
async def test_crawler_connection():
    """Test the Pexels API connection and configuration"""
    try:
        pexels_config = get_pexels_config()
        
        if not pexels_config.get("pexels_secret_key"):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Pexels secret key not configured",
                    "message": "Please set PEXELS_SECRET_KEY environment variable"
                }
            )
        
        # Test a simple search request
        async with PexelsCarCrawler() as crawler:
            test_result = await crawler.search_cars("car", page=1, per_page=1)
            
            if test_result and "photos" in test_result:
                return {
                    "status": "success",
                    "message": "Pexels API connection successful",
                    "test_result": {
                        "photos_found": len(test_result.get("photos", [])),
                        "total_results": test_result.get("total_results", 0)
                    }
                }
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "API test failed",
                        "message": "Could not retrieve photos from Pexels API"
                    }
                )
                
    except Exception as e:
        logger.error(f"Test connection error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Connection test failed",
                "message": str(e)
            }
        )

@router.get("/crawler/config")
async def get_crawler_config():
    """Get the crawler configuration"""
    pexels_config = get_pexels_config()
    
    return {
        "pexels_config": pexels_config,
        "available_endpoints": [
            "POST /api/v1/crawler/start - Start the Pexels crawler",
            "GET /api/v1/crawler/status - Get Pexels crawler status",
            "POST /api/v1/crawler/stop - Stop the Pexels crawler",
            "GET /api/v1/crawler/test - Test Pexels API connection",
            "GET /api/v1/crawler/config - Get configuration"
        ]
    }
