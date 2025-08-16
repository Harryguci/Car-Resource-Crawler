import asyncio
from numbers import Number
import httpx
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
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


class BingCrawler:
    """Crawl Bing image search HTML for direct image links and persist records.

    Flow:
    - Fetch HTML from Bing Images (no API) with query.
    - Extract candidate direct image URLs from HTML (handles murl/mediaurl and generic https links).
    - Verify which URLs are images by checking Content-Type.
    - Save DB record first, then download to blob/bing and update status.
    """

    def __init__(self, resource_dir: Optional[Path] = None):
        self.client: Optional[httpx.AsyncClient] = None
        self.db_session: Optional[SessionLocal] = None
        self.image_service: Optional[ImageResourceService] = None
        self.resource_dir: Path = Path(resource_dir) if resource_dir else Path("blob/bing")
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

        self.client = httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True)

        self.db_session = SessionLocal()
        self.image_service = ImageResourceService(self.db_session)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.client:
            await self.client.aclose()
        if self.db_session:
            self.db_session.close()

    async def fetch_bing_html(self, query: str, first: Number = 1) -> Optional[str]:
        if not self.client:
            raise RuntimeError("Client not initialized")

        base_url = "https://www.bing.com/images/search"
        params = {
            "q": query,
            # the 'first' param is the index of the first result (1-based typically)
            "first": first,
            # keep simple; Bing will still render results
        }

        try:
            response = await self.client.get(base_url, params=params)
            if response.status_code == 200:
                return response.text
            logger.error(f"Bing search failed: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching Bing HTML: {e}")
            self.stats["errors"] += 1
            return None

    @staticmethod
    def _unescape_bing_json_url(url: str) -> str:
        # Unescape common JSON-escaped sequences found in Bing's inline data
        return (
            url.replace("\\/", "/")
               .replace("\\u0026", "&")
               .replace("&amp;", "&")
        )

    def _extract_urls_from_html(self, html: str) -> List[str]:
        urls_set: Set[str] = set()

        # 1) Extract from inline JSON "murl":"https://..."
        for m in re.findall(r'"murl":"(https://[^"]+)"', html):
            urls_set.add(self._unescape_bing_json_url(m))

        # 2) Extract generic https URLs
        for u in re.findall(r"https://[^\s'\"<>]+", html):
            urls_set.add(u)

        self.stats["found_urls"] = len(urls_set)

        # Normalize: resolve Bing wrappers like mediaurl= in query strings
        normalized: Set[str] = set()
        for url in urls_set:
            try:
                if "mediaurl=" in url or "imgurl=" in url:
                    parsed = urlparse(url)
                    qs = parse_qs(parsed.query)
                    for key in ("mediaurl", "imgurl", "murl"):
                        vals = qs.get(key)
                        if vals and vals[0].startswith("http"):
                            normalized.add(self._unescape_bing_json_url(vals[0]))
                            break
                    else:
                        normalized.add(url)
                else:
                    normalized.add(url)
            except Exception:
                normalized.add(url)

        # Filter out obvious non-image/noisy endpoints
        candidates: List[str] = []
        for u in normalized:
            if any(x in u for x in [
                "bing.com/images/search",
                "/th?id=",
                "/rp/",
                "/fd/ls/",
                "/hp/",
                "bing.com/ck/a",
                "bing.com/aclick",
                "/favicon",
                "/policies/",
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
            head = await self.client.head(url)
            if head.status_code == 405 or head.status_code >= 400:
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
                source="bing",
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

    async def crawl(self, query: str, max_links: int = 50, first: Number = 1) -> Dict[str, Any]:
        self.stats["start_time"] = datetime.utcnow().isoformat()

        html = await self.fetch_bing_html(query, first=first)
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
                    if ok and self.image_service:
                        downloaded += 1
                        self.image_service.update_download_status(image_id, "completed")  # type: ignore[attr-defined]
                    elif self.image_service:
                        self.image_service.update_download_status(image_id, "failed", "Download failed")  # type: ignore[attr-defined]

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


async def run_bing_crawler(query: str, max_links: int = 50, first: Number = 1) -> Dict[str, Any]:
    async with BingCrawler() as crawler:
        return await crawler.crawl(query=query, max_links=max_links, first=first)