from fastapi import APIRouter, BackgroundTasks, HTTPException
from src.backgroundworker.google_crawler import GoogleCrawler
from src.config.logging_config import get_logger
import asyncio
from typing import Dict, Any
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter()

# Google crawler globals
google_crawler_instance: GoogleCrawler = None
google_crawler_task: asyncio.Task = None
google_crawler_status = {
    "is_running": False,
    "start_time": None,
    "last_update": None,
    "query": None,
    "progress": {
        "saved": 0,
        "downloaded": 0
    }
}

@router.post("/google_crawler/start")
async def start_google_crawler(
    background_tasks: BackgroundTasks,
    query: str,
    max_links: int = 50,
    start: int = 0,
    loops: int = 50
):
    """Start the Google image crawler in the background"""
    global google_crawler_instance, google_crawler_task, google_crawler_status
    
    if google_crawler_status["is_running"]:
        raise HTTPException(status_code=400, detail="Google crawler is already running")
    
    # Update status
    google_crawler_status.update({
        "is_running": True,
        "start_time": datetime.now().isoformat(),
        "last_update": datetime.now().isoformat(),
        "query": query,
        "progress": {
            "saved": 0,
            "downloaded": 0
        },
        "loops": loops,
        "max_links": max_links,
        "start_offset": start
    })
    
    async def run_crawler():
        global google_crawler_instance, google_crawler_status
        try:
            async with GoogleCrawler() as crawler:
                google_crawler_instance = crawler
                cumulative_saved = 0
                cumulative_downloaded = 0
                last_result: Dict[str, Any] = {}

                for i in range(max(1, loops)):
                    current_start = start + i * max_links
                    result = await crawler.crawl(query=query, max_links=max_links, start=current_start)
                    last_result = result
                    cumulative_saved += result.get("saved", 0)
                    cumulative_downloaded += result.get("downloaded", 0)

                    google_crawler_status.update({
                        "last_update": datetime.now().isoformat(),
                        "progress": {
                            "saved": cumulative_saved,
                            "downloaded": cumulative_downloaded
                        },
                        "current_iteration": i + 1,
                        "current_start": current_start
                    })

                    logger.info(
                        f"Google crawl iteration {i+1}/{loops} done: "
                        f"saved={result.get('saved')}, downloaded={result.get('downloaded')} (start={current_start})"
                    )

                # Update final status
                google_crawler_status.update({
                    "is_running": False,
                    "last_update": datetime.now().isoformat(),
                    "final_result": last_result,
                })

                logger.info(
                    f"Google crawler completed all iterations: "
                    f"saved={cumulative_saved}, downloaded={cumulative_downloaded}"
                )
        except asyncio.CancelledError:
            google_crawler_status.update({
                "is_running": False,
                "last_update": datetime.now().isoformat(),
                "status": "stopped"
            })
            raise
        except Exception as e:
            logger.error(f"Google crawler error: {str(e)}")
            google_crawler_status.update({
                "is_running": False,
                "last_update": datetime.now().isoformat(),
                "error": str(e)
            })
        finally:
            google_crawler_instance = None
    
    # Start background task
    google_crawler_task = asyncio.create_task(run_crawler())
    
    return {
        "message": "Google crawler started successfully",
        "query": query,
        "max_links": max_links,
        "start": start,
        "loops": loops,
        "status": "running"
    }

@router.post("/google_crawler/stop")
async def stop_google_crawler():
    """Stop the running Google crawler"""
    global google_crawler_task, google_crawler_status
    
    if not google_crawler_status["is_running"]:
        raise HTTPException(status_code=400, detail="No Google crawler is currently running")
    
    if google_crawler_task and not google_crawler_task.done():
        google_crawler_task.cancel()
        try:
            await google_crawler_task
        except asyncio.CancelledError:
            pass
    
    google_crawler_status.update({
        "is_running": False,
        "last_update": datetime.now().isoformat(),
        "status": "stopped"
    })
    
    return {
        "message": "Google crawler stopped successfully",
        "status": "stopped"
    }
