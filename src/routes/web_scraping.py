from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from src.backgroundworker.web_scaping_worker import WebScapingWorker
from src.config.logging_config import get_logger
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

logger = get_logger(__name__)

router = APIRouter()

# Web Scraping Worker globals
web_scraping_worker_instance: Optional[WebScapingWorker] = None
web_scraping_worker_task: Optional[asyncio.Task] = None
web_scraping_worker_status = {
    "is_running": False,
    "start_time": None,
    "last_update": None,
    "source_url": None,
    "query": None,
    "progress": {
        "saved": 0,
        "downloaded": 0
    }
}

@router.post("/web_scraping/start")
async def start_web_scraping(
    background_tasks: BackgroundTasks,
    url: str,
    query: str = "",
    max_links: int = 50,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    delay: float = 0.25,
    source_name: str = "web_scraping",
    resource_dir: Optional[str] = None,
    url_patterns: Optional[List[str]] = None,
    extraction_patterns: Optional[List[str]] = None
):
    """Start the web scraping worker in the background"""
    global web_scraping_worker_instance, web_scraping_worker_task, web_scraping_worker_status
    
    if web_scraping_worker_status["is_running"]:
        raise HTTPException(status_code=400, detail="Web scraping worker is already running")
    
    # Update status
    web_scraping_worker_status.update({
        "is_running": True,
        "start_time": datetime.now().isoformat(),
        "last_update": datetime.now().isoformat(),
        "source_url": url,
        "query": query,
        "progress": {
            "saved": 0,
            "downloaded": 0
        },
        "max_links": max_links,
        "method": method,
        "delay": delay
    })
    
    async def run_web_scraping():
        global web_scraping_worker_instance, web_scraping_worker_status
        try:
            # Create worker with custom configuration
            worker = WebScapingWorker(
                resource_dir=Path(resource_dir) if resource_dir else None,
                source_name=source_name,
                url_patterns=url_patterns,
                extraction_patterns=extraction_patterns
            )
            
            async with worker as scraper:
                web_scraping_worker_instance = scraper
                
                # Set custom patterns if provided
                if url_patterns:
                    scraper.set_url_patterns(url_patterns)
                if extraction_patterns:
                    scraper.set_extraction_patterns(extraction_patterns)
                if headers:
                    scraper.set_default_headers(headers)
                
                # Automatically enable advanced measures for Vecteezy
                if "vecteezy.com" in url:
                    scraper.enable_advanced_anti_bot_measures()
                    scraper.simulate_human_behavior()
                    scraper.set_request_delay(2.0, 5.0)
                    logger.info("Automatically enabled advanced anti-bot measures for Vecteezy")
                
                result = await scraper.crawl(
                    url=url,
                    query=query,
                    max_links=max_links,
                    headers=headers,
                    params=params,
                    method=method,
                    data=data,
                    delay=delay
                )
                
                # Update final status
                web_scraping_worker_status.update({
                    "is_running": False,
                    "last_update": datetime.now().isoformat(),
                    "final_result": result,
                    "progress": {
                        "saved": result.get("saved", 0),
                        "downloaded": result.get("downloaded", 0)
                    }
                })
                
                logger.info(f"Web scraping completed: {result}")
                
        except Exception as e:
            logger.error(f"Web scraping error: {str(e)}")
            web_scraping_worker_status.update({
                "is_running": False,
                "last_update": datetime.now().isoformat(),
                "error": str(e)
            })
        finally:
            web_scraping_worker_instance = None
    
    # Start background task
    web_scraping_worker_task = asyncio.create_task(run_web_scraping())
    
    return {
        "message": "Web scraping worker started successfully",
        "url": url,
        "query": query,
        "max_links": max_links,
        "method": method,
        "delay": delay,
        "source_name": source_name,
        "status": "running"
    }

@router.post("/web_scraping/start_multiple")
async def start_web_scraping_multiple(
    background_tasks: BackgroundTasks,
    sources: List[Dict[str, Any]],
    max_links_per_source: int = 50,
    delay_between_sources: float = 1.0,
    source_name: str = "web_scraping_multiple",
    resource_dir: Optional[str] = None
):
    """Start the web scraping worker for multiple sources in the background"""
    global web_scraping_worker_instance, web_scraping_worker_task, web_scraping_worker_status
    
    if web_scraping_worker_status["is_running"]:
        raise HTTPException(status_code=400, detail="Web scraping worker is already running")
    
    # Update status
    web_scraping_worker_status.update({
        "is_running": True,
        "start_time": datetime.now().isoformat(),
        "last_update": datetime.now().isoformat(),
        "source_url": f"Multiple sources ({len(sources)})",
        "query": "Multiple queries",
        "progress": {
            "saved": 0,
            "downloaded": 0
        },
        "max_links": max_links_per_source,
        "method": "Multiple",
        "delay": delay_between_sources
    })
    
    async def run_multiple_web_scraping():
        global web_scraping_worker_instance, web_scraping_worker_status
        try:
            # Create worker
            worker = WebScapingWorker(
                resource_dir=Path(resource_dir) if resource_dir else None,
                source_name=source_name
            )
            
            async with worker as scraper:
                web_scraping_worker_instance = scraper
                
                result = await scraper.crawl_multiple_sources(
                    sources=sources,
                    max_links_per_source=max_links_per_source,
                    delay_between_sources=delay_between_sources
                )
                
                # Update final status
                web_scraping_worker_status.update({
                    "is_running": False,
                    "last_update": datetime.now().isoformat(),
                    "final_result": result,
                    "progress": {
                        "saved": result.get("total_stats", {}).get("total_saved", 0),
                        "downloaded": result.get("total_stats", {}).get("total_downloaded", 0)
                    }
                })
                
                logger.info(f"Multiple web scraping completed: {result}")
                
        except Exception as e:
            logger.error(f"Multiple web scraping error: {str(e)}")
            web_scraping_worker_status.update({
                "is_running": False,
                "last_update": datetime.now().isoformat(),
                "error": str(e)
            })
        finally:
            web_scraping_worker_instance = None
    
    # Start background task
    web_scraping_worker_task = asyncio.create_task(run_multiple_web_scraping())
    
    return {
        "message": "Multiple web scraping worker started successfully",
        "sources_count": len(sources),
        "max_links_per_source": max_links_per_source,
        "delay_between_sources": delay_between_sources,
        "source_name": source_name,
        "status": "running"
    }

@router.get("/web_scraping/status")
async def get_web_scraping_status():
    """Get the current status of the web scraping worker"""
    global web_scraping_worker_instance, web_scraping_worker_status
    
    # Get current stats if worker is running
    current_stats = None
    if web_scraping_worker_instance and web_scraping_worker_status["is_running"]:
        current_stats = web_scraping_worker_instance.stats
        # Update progress based on current stats
        if current_stats:
            web_scraping_worker_status["progress"]["saved"] = current_stats.get("saved_records", 0)
            web_scraping_worker_status["progress"]["downloaded"] = current_stats.get("downloaded", 0)
            web_scraping_worker_status["last_update"] = datetime.now().isoformat()
    
    return {
        "web_scraping_status": web_scraping_worker_status,
        "current_stats": current_stats,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/web_scraping/stop")
async def stop_web_scraping():
    """Stop the running web scraping worker"""
    global web_scraping_worker_task, web_scraping_worker_status
    
    if not web_scraping_worker_status["is_running"]:
        raise HTTPException(status_code=400, detail="No web scraping worker is currently running")
    
    # Cancel the background task
    if web_scraping_worker_task and not web_scraping_worker_task.done():
        web_scraping_worker_task.cancel()
        try:
            await web_scraping_worker_task
        except asyncio.CancelledError:
            pass
    
    web_scraping_worker_status.update({
        "is_running": False,
        "last_update": datetime.now().isoformat(),
        "status": "stopped"
    })
    
    return {
        "message": "Web scraping worker stopped successfully",
        "status": "stopped"
    }

@router.post("/web_scraping/test")
async def test_web_scraping_connection(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None
):
    """Test web scraping connection to a specific URL"""
    try:
        async with WebScapingWorker() as worker:
            html = await worker.fetch_html(url, headers, params, method, data)
            
            if html:
                # Try to extract some URLs to test the extraction logic
                urls = worker._extract_urls_from_html(html)
                
                return {
                    "status": "success",
                    "message": "Web scraping connection successful",
                    "url": url,
                    "html_length": len(html),
                    "urls_found": len(urls),
                    "sample_urls": urls[:5] if urls else []
                }
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Connection test failed",
                        "message": f"Could not fetch HTML from {url}"
                    }
                )
                
    except Exception as e:
        logger.error(f"Web scraping test connection error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Connection test failed",
                "message": str(e)
            }
        )

@router.get("/web_scraping/config")
async def get_web_scraping_config():
    """Get the web scraping worker configuration and available patterns"""
    return {
        "default_url_patterns": [
            r'"murl":"(https://[^"]+)"',  # Bing-style murl
            r'"imageUrl":"(https://[^"]+)"',  # Generic imageUrl
            r'"src":"(https://[^"]+)"',  # Generic src
            r'"url":"(https://[^"]+)"',  # Generic url
            r'<img[^>]+src="(https://[^"]+)"',  # HTML img tags
            r'https://[^\s\'\"<>]+',  # Generic https URLs
        ],
        "default_extraction_patterns": [
            "mediaurl=",
            "imgurl=",
            "murl=",
            "imageurl=",
        ],
        "default_headers": {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "upgrade-insecure-requests": "1",
        },
        "available_endpoints": [
            "POST /api/v1/web_scraping/start - Start web scraping for a single source",
            "POST /api/v1/web_scraping/start_multiple - Start web scraping for multiple sources",
            "GET /api/v1/web_scraping/status - Get web scraping worker status",
            "POST /api/v1/web_scraping/stop - Stop the web scraping worker",
            "POST /api/v1/web_scraping/test - Test web scraping connection",
            "GET /api/v1/web_scraping/config - Get configuration"
        ]
    }
