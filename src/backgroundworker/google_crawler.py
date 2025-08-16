# TODO: implement Google Crawler to get all images from Google image search page (html doc) depends on query (as input)
# Read docs/Google_api.md to understand how to get images from Google image search page
# Use httpx to get the html doc
# Save the url resource record into Database like Pexels Services

import asyncio
from numbers import Number
import httpx
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import hashlib
import time

import aiofiles

from src.database.connection import SessionLocal
from src.services.image_resource_service import ImageResourceService
from src.models.image_resource import ImageResourceCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleCrawler:
    """Crawl Google image search HTML for direct image links and persist records.

    Flow:
    - Fetch HTML from Google Images (no API) with query.
    - Extract all https URLs in the HTML.
    - Normalize and resolve any Google redirect wrappers (e.g. imgurl param).
    - Verify which URLs are images by checking Content-Type.
    - Save DB record first, then download to blob/google and update status.
    """

    def __init__(self, resource_dir: Optional[Path] = None):
        self.client: Optional[httpx.AsyncClient] = None
        self.db_session: Optional[SessionLocal] = None
        self.image_service: Optional[ImageResourceService] = None
        self.resource_dir: Path = Path(resource_dir) if resource_dir else Path("blob/google")
        self.resource_dir.mkdir(parents=True, exist_ok=True)

        self.stats: Dict[str, Any] = {
            "start_time": None,
            "found_urls": 0,
            "unique_urls": 0,
            "image_candidates": 0,
            "saved_records": 0,
            "downloaded": 0,
            "errors": 0,
        }

    async def __aenter__(self):
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            ),
            "upgrade-insecure-requests": "1",
        }

        # Keep it simple: no special cookies by default
        self.client = httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True)

        self.db_session = SessionLocal()
        self.image_service = ImageResourceService(self.db_session)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.client:
            await self.client.aclose()
        if self.db_session:
            self.db_session.close()

    async def fetch_google_html(self, query: str, start: Number = 0) -> Optional[str]:
        if not self.client:
            raise RuntimeError("Client not initialized")

        # Image layout: udm=2 focuses on image results; tbm=isch is classic image search
        base_url = "https://www.google.com/search"
        params = {
            "q": query,
            "udm": "2",
            "hl": "en",
            "tbm": "isch",
            "source": "lnms",
            "start": start,
        }

        try:
            response = await self.client.get(base_url, params=params)
            if response.status_code == 200:
                return response.text
            logger.error(f"Google search failed: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching Google HTML: {e}")
            self.stats["errors"] += 1
            return None

    def _extract_urls_from_html(self, html: str) -> List[str]:
        # Find all https URLs present in text
        urls: List[str] = re.findall(r"https://[^\s\'\"<>]+", html)
        self.stats["found_urls"] = len(urls)

        # Normalize: resolve Google imgres wrappers to direct imgurl if present
        normalized: Set[str] = set()
        for url in urls:
            if "imgurl=" in url:
                try:
                    parsed = urlparse(url)
                    qs = parse_qs(parsed.query)
                    imgurl_vals = qs.get("imgurl")
                    if imgurl_vals and imgurl_vals[0].startswith("http"):
                        normalized.add(imgurl_vals[0])
                        continue
                except Exception:
                    pass
            normalized.add(url)

        # Filter out obvious non-image hosts if desired; keep thumbnails too
        candidates: List[str] = []
        for u in normalized:
            # Skip some known non-image noisy endpoints
            if any(host in u for host in [
                "google.com/search", 
                "googleusercontent.com/gen_", 
                "/maps/",
                "/policies/",
                "/images/branding/",
                "/logo",
            ]):
                continue
            candidates.append(u)

        # Deduplicate while preserving order
        seen: Set[str] = set()
        unique_urls: List[str] = []
        for u in candidates:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        self.stats["unique_urls"] = len(unique_urls)
        return unique_urls

    async def _head_content_type(self, url: str) -> Optional[str]:
        if not self.client:
            return None
        try:
            # Try HEAD first
            head = await self.client.head(url)
            if head.status_code == 405 or head.status_code >= 400:
                # Some servers disallow HEAD; try a minimal GET
                get = await self.client.get(url, headers={"Range": "bytes=0-0"})
                if get.status_code >= 400:
                    return None
                return get.headers.get("content-type")
            return head.headers.get("content-type")
        except Exception:
            return None

    @staticmethod
    def _infer_extension_from_content_type(content_type: Optional[str]) -> Optional[str]:
        if not content_type:
            return None
        mapping = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
            "image/bmp": "bmp",
            "image/tiff": "tiff",
            "image/svg+xml": "svg",
        }
        for key, ext in mapping.items():
            if content_type.lower().startswith(key):
                return ext
        return None

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        cleaned = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_", "."))
        return cleaned.replace(" ", "_")

    def _generate_filename(self, url: str, query: str, content_type: Optional[str]) -> str:
        ext = self._infer_extension_from_content_type(content_type) or "jpg"
        query_slug = self._sanitize_filename(query.strip().replace(" ", "_")) or "query"
        ts_ns = time.time_ns()
        h = hashlib.sha1(str(ts_ns).encode()).hexdigest()[:12]
        return f"{query_slug}_{h}.{ext}"

    def _check_image_exists(self, image_url: str) -> bool:
        try:
            if not self.image_service:
                return False
            return self.image_service.get_image_resource_by_url(image_url) is not None
        except Exception as e:
            logger.error(f"Error checking existing URL: {e}")
            return False

    def _save_image_record(self, image_url: str, filename: str, query: str, content_type: Optional[str]) -> Optional[str]:
        try:
            if not self.image_service:
                return None
            ext = self._infer_extension_from_content_type(content_type)
            image_data = ImageResourceCreate(
                url=image_url,
                filename=filename,
                file_path=str(self.resource_dir / filename),
                source="google",
                search_query=query,
                tags=[query] if query else None,
                format=ext,
            )
            saved = self.image_service.create_image_resource(image_data)
            self.stats["saved_records"] += 1
            return saved.id
        except Exception as e:
            logger.error(f"Error saving DB record: {e}")
            self.stats["errors"] += 1
            return None

    async def _download_image(self, url: str, filename: str) -> bool:
        if not self.client:
            return False
        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                logger.warning(f"Download failed ({response.status_code}) for {url}")
                return False
            file_path = self.resource_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(response.content)
            self.stats["downloaded"] += 1
            return True
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            self.stats["errors"] += 1
            return False

    async def crawl(self, query: str, max_links: int = 50, start: Number = 0) -> Dict[str, Any]:
        self.stats["start_time"] = datetime.utcnow().isoformat()

        html = await self.fetch_google_html(query, start=start)
        if not html:
            return {"success": False, "reason": "failed_to_fetch_html", "stats": self.stats}

        urls = self._extract_urls_from_html(html)
        self.stats["image_candidates"] = len(urls)

        saved = 0
        downloaded = 0

        for url in urls[:max_links]:
            try:
                if self._check_image_exists(url):
                    continue

                content_type = await self._head_content_type(url)
                if not content_type or not content_type.lower().startswith("image/"):
                    continue

                filename = self._generate_filename(url, query, content_type)
                image_id = self._save_image_record(url, filename, query, content_type)

                if image_id:
                    saved += 1
                    ok = await self._download_image(url, filename)
                    if ok:
                        downloaded += 1
                        self.image_service.update_download_status(image_id, "completed")  # type: ignore[attr-defined]
                    else:
                        self.image_service.update_download_status(image_id, "failed", "Download failed")  # type: ignore[attr-defined]

                # be a little polite
                await asyncio.sleep(0.25)
            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                self.stats["errors"] += 1

        return {
            "success": True,
            "query": query,
            "saved": saved,
            "downloaded": downloaded,
            "stats": self.stats,
        }


async def run_google_crawler(query: str, max_links: int = 50, start: Number = 0) -> Dict[str, Any]:
    async with GoogleCrawler() as crawler:
        return await crawler.crawl(query=query, max_links=max_links, start=start)