from fastapi import APIRouter, BackgroundTasks, HTTPException
from src.backgroundworker.bing_crawler import BingCrawler
from src.config.logging_config import get_logger
import asyncio
from typing import Dict, Any
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter()

# Bing crawler globals
bing_crawler_instance: BingCrawler = None
bing_crawler_task: asyncio.Task = None
bing_crawler_status = {
    "is_running": False,
    "start_time": None,
    "last_update": None,
    "query": None,
    "progress": {
        "saved": 0,
        "downloaded": 0
    }
}

@router.post("/bing_crawler/start")
async def start_bing_crawler(
    background_tasks: BackgroundTasks,
    query: str,
    max_links: int = 50,
    first: int = 1,
    loops: int = 50
):
    """Start the Bing image crawler in the background"""
    global bing_crawler_instance, bing_crawler_task, bing_crawler_status

    if bing_crawler_status["is_running"]:
        raise HTTPException(status_code=400, detail="Bing crawler is already running")

    # Update status
    bing_crawler_status.update({
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
        "start_first": first
    })

    async def run_crawler():
        global bing_crawler_instance, bing_crawler_status
        try:
            async with BingCrawler() as crawler:
                bing_crawler_instance = crawler
                cumulative_saved = 0
                cumulative_downloaded = 0
                last_result: Dict[str, Any] = {}

                for i in range(max(1, loops)):
                    current_first = first + i * max_links
                    result = await crawler.crawl(query=query, max_links=max_links, first=current_first)
                    last_result = result
                    cumulative_saved += result.get("saved", 0)
                    cumulative_downloaded += result.get("downloaded", 0)

                    bing_crawler_status.update({
                        "last_update": datetime.now().isoformat(),
                        "progress": {
                            "saved": cumulative_saved,
                            "downloaded": cumulative_downloaded
                        },
                        "current_iteration": i + 1,
                        "current_first": current_first
                    })

                    logger.info(
                        f"Bing crawl iteration {i+1}/{loops} done: "
                        f"saved={result.get('saved')}, downloaded={result.get('downloaded')} (first={current_first})"
                    )

                # Update final status
                bing_crawler_status.update({
                    "is_running": False,
                    "last_update": datetime.now().isoformat(),
                    "final_result": last_result,
                })

                logger.info(
                    f"Bing crawler completed all iterations: "
                    f"saved={cumulative_saved}, downloaded={cumulative_downloaded}"
                )
        except asyncio.CancelledError:
            bing_crawler_status.update({
                "is_running": False,
                "last_update": datetime.now().isoformat(),
                "status": "stopped"
            })
            raise
        except Exception as e:
            logger.error(f"Bing crawler error: {str(e)}")
            bing_crawler_status.update({
                "is_running": False,
                "last_update": datetime.now().isoformat(),
                "error": str(e)
            })
        finally:
            bing_crawler_instance = None

    # Start background task
    bing_crawler_task = asyncio.create_task(run_crawler())

    return {
        "message": "Bing crawler started successfully",
        "query": query,
        "max_links": max_links,
        "first": first,
        "loops": loops,
        "status": "running"
    }

@router.post("/bing_crawler/stop")
async def stop_bing_crawler():
    """Stop the running Bing crawler"""
    global bing_crawler_task, bing_crawler_status

    if not bing_crawler_status["is_running"]:
        raise HTTPException(status_code=400, detail="No Bing crawler is currently running")

    if bing_crawler_task and not bing_crawler_task.done():
        bing_crawler_task.cancel()
        try:
            await bing_crawler_task
        except asyncio.CancelledError:
            pass

    bing_crawler_status.update({
        "is_running": False,
        "last_update": datetime.now().isoformat(),
        "status": "stopped"
    })

    return {
        "message": "Bing crawler stopped successfully",
        "status": "stopped"
    }
