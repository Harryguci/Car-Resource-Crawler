from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.routes import items, image_resources, pexels_crawler, google_crawler, bing_crawler, web_scraping
from src.config.settings import settings
from src.config.logging_config import setup_logging, get_logger
from src.utils.env_utils import validate_required_env_vars
from src.database.connection import init_db, close_db, Base, engine
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



# Include routers
app.include_router(items.router, prefix=settings.api_prefix, tags=["items"])
app.include_router(image_resources.router, prefix=settings.api_prefix, tags=["image_resources"])
app.include_router(pexels_crawler.router, prefix=settings.api_prefix, tags=["pexels_crawler"])
app.include_router(google_crawler.router, prefix=settings.api_prefix, tags=["google_crawler"])
app.include_router(bing_crawler.router, prefix=settings.api_prefix, tags=["bing_crawler"])
app.include_router(web_scraping.router, prefix=settings.api_prefix, tags=["web_scraping"])

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
        "crawlers_available": ["pexels", "google", "bing", "web_scraping"]
    }

@app.get("/config")
def get_config():
    """Get current configuration (useful for debugging)"""
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
        "crawlers_available": ["pexels", "google", "bing", "web_scraping"],
        "environment_validation": env_validation
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
    logger.info("Shutting down application...")
    
    # Close database connections
    try:
        close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    
    logger.info("Application shutdown complete")