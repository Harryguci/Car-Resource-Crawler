from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.routes import items
from src.routes import image_resources
from src.config.settings import settings
from src.config.logging_config import setup_logging, get_logger
from src.backgroundworker.car_crawler import PexelsCarCrawler, run_car_crawler
from src.utils.env_utils import get_pexels_config, validate_required_env_vars
from src.database.connection import init_db, close_db, Base, engine
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Setup logging configuration
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="A FastAPI project with proper structure and car image crawler",
    version=settings.version,
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



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

# Include routers
app.include_router(items.router, prefix=settings.api_prefix, tags=["items"])

# Image Resources routers
app.include_router(image_resources.router, prefix=settings.api_prefix, tags=["image_resources"])

@app.get("/")
def read_root():
    return {
        "message": f"Welcome to {settings.app_name}!",
        "version": settings.version,
        "environment": settings.environment,
        "debug": settings.debug,
        "features": ["car_image_crawler", "api_endpoints", "background_processing"]
    }

@app.get("/health")
def health_check():
    env_validation = validate_required_env_vars()
    return {
        "status": "healthy",
        "environment": settings.environment,
        "database_configured": settings.database_url is not None,
        "pexels_configured": env_validation.get("EXTERNAL_API_KEY", False),
        "crawler_status": crawler_status["is_running"]
    }

@app.get("/config")
def get_config():
    """Get current configuration (useful for debugging)"""
    pexels_config = get_pexels_config()
    env_validation = validate_required_env_vars()
    
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "debug": settings.debug,
        "host": settings.host,
        "port": settings.port,
        "api_prefix": settings.api_prefix,
        "database_configured": settings.database_url is not None,
        "redis_configured": settings.redis_url is not None,
        "external_api_configured": settings.external_api_key is not None,
        "pexels_config": {
            "base_url_configured": bool(pexels_config.get("pexels_base_url")),
            "secret_key_configured": bool(pexels_config.get("pexels_secret_key")),
            "resource_dir": pexels_config.get("resource_dir"),
            "request_frequency": pexels_config.get("request_frequency")
        },
        "environment_validation": env_validation
    }

# Car Crawler API Endpoints

@app.post("/api/v1/crawler/start")
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

@app.get("/api/v1/crawler/status")
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

@app.post("/api/v1/crawler/stop")
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

@app.get("/api/v1/crawler/test")
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

@app.get("/api/v1/crawler/config")
async def get_crawler_config():
    """Get the crawler configuration"""
    pexels_config = get_pexels_config()
    env_validation = validate_required_env_vars()
    
    return {
        "pexels_config": pexels_config,
        "environment_validation": env_validation,
        "available_endpoints": [
            "POST /api/v1/crawler/start - Start the crawler",
            "GET /api/v1/crawler/status - Get crawler status",
            "POST /api/v1/crawler/stop - Stop the crawler",
            "GET /api/v1/crawler/test - Test API connection",
            "GET /api/v1/crawler/config - Get configuration"
        ]
    }

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info(f"Starting {settings.app_name} v{settings.version}")
    logger.info(f"Environment: {settings.environment}")
    
    # Validate environment
    env_validation = validate_required_env_vars()
    missing_vars = [var for var, valid in env_validation.items() if not valid]
    if missing_vars:
        logger.warning(f"Missing or invalid environment variables: {missing_vars}")
    
    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Don't raise here to allow the app to start even if DB is not available

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    global crawler_task, crawler_status
    
    logger.info("Shutting down application...")
    
    # Stop any running crawler
    if crawler_status["is_running"] and crawler_task:
        crawler_task.cancel()
        try:
            await crawler_task
        except asyncio.CancelledError:
            pass
    
    # Close database connections
    try:
        close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    
    logger.info("Application shutdown complete")