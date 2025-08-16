import asyncio
import hashlib
import re
import time
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from urllib.parse import parse_qs, urlparse

import aiofiles
import httpx
from sqlalchemy.orm import Session

from src.config.logging_config import get_logger
from src.database.connection import SessionLocal
from src.models.image_resource import ImageResourceCreate
from src.services.image_resource_service import ImageResourceService

logger = get_logger(__name__)

Number = Union[int, float]


class WebScapingWorker:
    """Generic web scraping worker for crawling images from any HTML source.

    Flow:
    - Fetch HTML from any configurable URL with custom headers and query params.
    - Extract candidate direct image URLs from HTML using configurable patterns.
    - Verify which URLs are images by checking Content-Type.
    - Save DB record first, then download to blob and update status.
    - Supports multiple URL patterns and extraction strategies.
    """

    def __init__(
        self,
        resource_dir: Optional[Path] = None,
        source_name: str = "web_scraping",
        url_patterns: Optional[List[str]] = None,
        extraction_patterns: Optional[List[str]] = None,
    ):
        self.client: Optional[httpx.AsyncClient] = None
        self.db_session: Optional[SessionLocal] = None
        self.image_service: Optional[ImageResourceService] = None
        self.resource_dir: Path = Path(resource_dir) if resource_dir else Path(f"blob/{source_name}")
        self.source_name = source_name
        self.resource_dir.mkdir(parents=True, exist_ok=True)

        # Default URL patterns for common image sources
        self.url_patterns = url_patterns or [
            r'"murl":"(https://[^"]+)"',  # Bing-style murl
            r'"imageUrl":"(https://[^"]+)"',  # Generic imageUrl
            r'"src":"(https://[^"]+)"',  # Generic src
            r'"url":"(https://[^"]+)"',  # Generic url
            r'<img[^>]+src="(https://[^"]+)"',  # HTML img tags
            r'https://[^\s\'\"<>]+',  # Generic https URLs
        ]

        # Default extraction patterns for common image sources
        self.extraction_patterns = extraction_patterns or [
            "mediaurl=",
            "imgurl=",
            "murl=",
            "imageurl=",
        ]

        # Default headers for web scraping
        self.default_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            ),
            "upgrade-insecure-requests": "1",
        }

        self.stats: Dict[str, Any] = {
            "start_time": None,
            "found_urls": 0,
            "unique_urls": 0,
            "image_candidates": 0,
            "saved_records": 0,
            "downloaded": 0,
            "errors": 0,
            "source": source_name,
        }

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            headers=self.default_headers,
            timeout=30.0,
            follow_redirects=True
        )
        self.db_session = SessionLocal()
        self.image_service = ImageResourceService(self.db_session)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.client:
            await self.client.aclose()
        if self.db_session:
            self.db_session.close()

    async def fetch_html(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> Optional[str]:
        """Fetch HTML from any URL with custom headers and parameters."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        # Check if this is Vecteezy and use special handling
        if "vecteezy.com" in url:
            return await self._fetch_vecteezy_html(url, headers, params, method, data, max_retries, retry_delay)

        # Merge custom headers with defaults
        request_headers = {**self.default_headers}
        if headers:
            request_headers.update(headers)

        # Add more realistic headers to avoid 403
        enhanced_headers = {
            **request_headers,
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }

        for attempt in range(max_retries):
            try:
                if method.upper() == "GET":
                    response = await self.client.get(url, headers=enhanced_headers, params=params)
                elif method.upper() == "POST":
                    response = await self.client.post(url, headers=enhanced_headers, params=params, data=data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                # Handle different status codes
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 403:
                    logger.warning(f"Access forbidden (403) for {url} - attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        # Try with different user agent
                        enhanced_headers["User-Agent"] = self._get_rotating_user_agent()
                        # Rotate session on 403
                        if attempt == 1:
                            self.rotate_session()
                        wait_time = await self._apply_retry_strategy(attempt, retry_delay)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Failed to access {url} after {max_retries} attempts - 403 Forbidden")
                        self.stats["errors"] += 1
                        return None
                elif response.status_code == 429:
                    logger.warning(f"Rate limited (429) for {url} - attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        wait_time = await self._apply_retry_strategy(attempt, retry_delay)
                        logger.info(f"Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Rate limited for {url} after {max_retries} attempts")
                        self.stats["errors"] += 1
                        return None
                elif response.status_code in [500, 502, 503, 504]:
                    logger.warning(f"Server error ({response.status_code}) for {url} - attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        wait_time = await self._apply_retry_strategy(attempt, retry_delay)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Server error for {url} after {max_retries} attempts")
                        self.stats["errors"] += 1
                        return None
                else:
                    logger.error(f"HTTP request failed: {response.status_code} for {url}")
                    self.stats["errors"] += 1
                    return None

            except Exception as e:
                logger.error(f"Error fetching HTML from {url} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    self.stats["errors"] += 1
                    return None

        return None

    async def _fetch_vecteezy_html(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        max_retries: int = 5,
        retry_delay: float = 2.0,
    ) -> Optional[str]:
        """Special method for handling Vecteezy.com with advanced anti-bot bypass."""
        logger.info(f"Using Vecteezy-specific fetching strategy for {url}")
        
        # Enable advanced anti-bot measures
        self.enable_advanced_anti_bot_measures()
        
        # Get Vecteezy-specific headers
        vecteezy_headers = self._get_vecteezy_specific_headers()
        if headers:
            vecteezy_headers.update(headers)

        for attempt in range(max_retries):
            try:
                # Add random delay before request
                await asyncio.sleep(random.uniform(1.0, 3.0))
                
                # Rotate User-Agent on each attempt
                vecteezy_headers["User-Agent"] = self._get_rotating_user_agent()
                
                # Add random IP headers
                vecteezy_headers["X-Forwarded-For"] = self._get_random_ip()
                vecteezy_headers["X-Real-IP"] = self._get_random_ip()
                
                # Try to fetch the page based on method
                if method.upper() == "GET":
                    response = await self.client.get(url, headers=vecteezy_headers, params=params, timeout=60.0)
                elif method.upper() == "POST":
                    response = await self.client.post(url, headers=vecteezy_headers, params=params, data=data, timeout=60.0)
                else:
                    logger.error(f"Unsupported HTTP method for Vecteezy: {method}")
                    return None
                
                if response.status_code == 200:
                    logger.info(f"Successfully fetched Vecteezy page: {url}")
                    return response.text
                elif response.status_code == 403:
                    logger.warning(f"Vecteezy access forbidden (403) - attempt {attempt + 1}/{max_retries}")
                    
                    if attempt < max_retries - 1:
                        # Rotate session
                        self.rotate_session()
                        
                        # Try different strategies
                        if attempt == 1:
                            # Add referer from Google search
                            vecteezy_headers["Referer"] = "https://www.google.com/search?q=vecteezy+bus+photos"
                        elif attempt == 2:
                            # Try with different accept headers
                            vecteezy_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                        elif attempt == 3:
                            # Try with mobile user agent
                            vecteezy_headers["User-Agent"] = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
                            vecteezy_headers["Sec-Ch-Ua-Mobile"] = "?1"
                        
                        # Exponential backoff with jitter
                        wait_time = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                        logger.info(f"Waiting {wait_time:.2f}s before retry...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Failed to access Vecteezy {url} after {max_retries} attempts")
                        self.stats["errors"] += 1
                        return None
                else:
                    logger.error(f"Vecteezy HTTP error: {response.status_code} for {url}")
                    self.stats["errors"] += 1
                    return None
                    
            except Exception as e:
                logger.error(f"Error fetching Vecteezy HTML (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                    continue
                else:
                    self.stats["errors"] += 1
                    return None
        
        return None

    def get_error_analysis(self, status_code: int, url: str) -> Dict[str, Any]:
        """Analyze HTTP errors and provide suggestions for resolution."""
        analysis = {
            "status_code": status_code,
            "url": url,
            "description": "",
            "possible_causes": [],
            "suggestions": [],
            "retry_recommended": False
        }

        if status_code == 403:
            analysis.update({
                "description": "Access Forbidden - The server understood the request but refuses to authorize it",
                "possible_causes": [
                    "IP address blocked or blacklisted",
                    "User-Agent string detected as bot",
                    "Geographic restrictions",
                    "Rate limiting",
                    "Missing or invalid authentication",
                    "Anti-bot protection active"
                ],
                "suggestions": [
                    "Use proxy rotation",
                    "Rotate User-Agent strings",
                    "Add realistic browser headers",
                    "Implement session rotation",
                    "Increase delays between requests",
                    "Use residential proxies if available"
                ],
                "retry_recommended": True
            })
        elif status_code == 429:
            analysis.update({
                "description": "Too Many Requests - Rate limit exceeded",
                "possible_causes": [
                    "Too many requests in short time",
                    "Rate limiting by IP address",
                    "Rate limiting by User-Agent",
                    "Rate limiting by session"
                ],
                "suggestions": [
                    "Increase delays between requests",
                    "Implement exponential backoff",
                    "Use proxy rotation",
                    "Rotate User-Agent strings",
                    "Implement request queuing"
                ],
                "retry_recommended": True
            })
        elif status_code in [500, 502, 503, 504]:
            analysis.update({
                "description": f"Server Error ({status_code}) - Server-side issue",
                "possible_causes": [
                    "Server overload",
                    "Maintenance mode",
                    "Database connection issues",
                    "Backend service failures"
                ],
                "suggestions": [
                    "Wait and retry later",
                    "Use exponential backoff",
                    "Check if service is in maintenance",
                    "Contact site administrators if persistent"
                ],
                "retry_recommended": True
            })
        elif status_code == 404:
            analysis.update({
                "description": "Not Found - Resource doesn't exist",
                "possible_causes": [
                    "URL is incorrect",
                    "Resource was removed",
                    "Typo in URL",
                    "Site structure changed"
                ],
                "suggestions": [
                    "Verify URL correctness",
                    "Check if resource moved",
                    "Update URL patterns",
                    "Implement URL validation"
                ],
                "retry_recommended": False
            })

        return analysis

    def get_vecteezy_recommendations(self) -> Dict[str, Any]:
        """Get specific recommendations for scraping Vecteezy.com."""
        return {
            "site": "Vecteezy.com",
            "difficulty": "Very High",
            "anti_bot_protection": "Advanced",
            "recommended_strategies": [
                "Use enable_advanced_anti_bot_measures()",
                "Use simulate_human_behavior()",
                "Set longer delays (2-5 seconds)",
                "Use proxy rotation",
                "Rotate User-Agent strings",
                "Add realistic referer headers",
                "Use session rotation",
                "Implement exponential backoff"
            ],
            "headers_to_include": [
                "Referer: https://www.google.com/search?q=vecteezy+photos",
                "Origin: https://www.vecteezy.com",
                "Host: www.vecteezy.com",
                "X-Forwarded-For: [random IP]",
                "X-Real-IP: [random IP]"
            ],
            "timing_recommendations": {
                "min_delay": 2.0,
                "max_delay": 5.0,
                "retry_delay": 2.0,
                "max_retries": 5
            },
            "alternative_approaches": [
                "Use residential proxies",
                "Implement browser automation (Selenium)",
                "Use headless browsers",
                "Consider API alternatives if available"
            ]
        }

    def get_site_specific_config(self, url: str) -> Dict[str, Any]:
        """Get site-specific configuration recommendations."""
        if "vecteezy.com" in url:
            return self.get_vecteezy_recommendations()
        elif "unsplash.com" in url:
            return {
                "site": "Unsplash.com",
                "difficulty": "Medium",
                "recommendations": ["Use standard anti-bot measures", "Respect rate limits"]
            }
        elif "pexels.com" in url:
            return {
                "site": "Pexels.com",
                "difficulty": "Low",
                "recommendations": ["Use API if available", "Standard scraping should work"]
            }
        else:
            return {
                "site": "Unknown",
                "difficulty": "Unknown",
                "recommendations": ["Start with basic anti-bot measures", "Monitor for 403/429 errors"]
            }

    def _get_random_user_agent(self) -> str:
        """Get a random user agent to avoid detection."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        ]
        return random.choice(user_agents)

    def set_proxy(self, proxy_url: str) -> None:
        """Set a proxy for the HTTP client."""
        if self.client:
            # Close existing client and create new one with proxy
            asyncio.create_task(self.client.aclose())
            self.client = httpx.AsyncClient(
                headers=self.default_headers,
                timeout=30.0,
                follow_redirects=True,
                proxies=proxy_url
            )

    def rotate_session(self) -> None:
        """Rotate the HTTP session to avoid detection."""
        if self.client:
            # Close existing client and create new one with fresh session
            asyncio.create_task(self.client.aclose())
            self.client = httpx.AsyncClient(
                headers=self.default_headers,
                timeout=30.0,
                follow_redirects=True
            )

    def simulate_human_behavior(self) -> None:
        """Enable human-like behavior simulation."""
        self.human_simulation = True
        self.min_delay = 2.0
        self.max_delay = 5.0
        
        # Add human-like headers
        human_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9,en;q=0.8",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        self.default_headers.update(human_headers)

    async def _human_delay(self) -> None:
        """Apply human-like delays between requests."""
        if hasattr(self, 'human_simulation') and self.human_simulation:
            # Random delay with human-like variation
            base_delay = random.uniform(self.min_delay, self.max_delay)
            # Add some randomness to make it more human-like
            jitter = random.uniform(-0.5, 1.0)
            final_delay = max(0.5, base_delay + jitter)
            logger.info(f"Human simulation: waiting {final_delay:.2f}s")
            await asyncio.sleep(final_delay)
        else:
            await self._smart_delay()

    def add_custom_headers(self, additional_headers: Dict[str, str]) -> None:
        """Add custom headers to the default headers."""
        self.default_headers.update(additional_headers)

    def set_request_delay(self, min_delay: float, max_delay: float) -> None:
        """Set random delay range between requests to avoid rate limiting."""
        self.min_delay = min_delay
        self.max_delay = max_delay

    async def _smart_delay(self) -> None:
        """Apply smart delay between requests."""
        if hasattr(self, 'min_delay') and hasattr(self, 'max_delay'):
            import random
            delay = random.uniform(self.min_delay, self.max_delay)
            await asyncio.sleep(delay)
        else:
            # Default delay
            await asyncio.sleep(0.25)

    def enable_anti_bot_measures(self) -> None:
        """Enable additional anti-bot detection avoidance measures."""
        # Add more realistic headers
        anti_bot_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9,en;q=0.8",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.default_headers.update(anti_bot_headers)

    def enable_advanced_anti_bot_measures(self) -> None:
        """Enable advanced anti-bot detection avoidance measures for heavily protected sites."""
        # Advanced browser fingerprinting headers
        advanced_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "DNT": "1",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "X-Forwarded-For": self._get_random_ip(),
            "X-Real-IP": self._get_random_ip(),
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "www.vecteezy.com",
            "X-Forwarded-Server": "www.vecteezy.com"
        }
        self.default_headers.update(advanced_headers)
        
        # Enable advanced features
        self.advanced_mode = True
        self.cookie_jar = {}
        self.session_id = self._generate_session_id()

    def _get_random_ip(self) -> str:
        """Generate a random IP address to avoid IP-based blocking."""
        import random
        return f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"

    def _generate_session_id(self) -> str:
        """Generate a unique session ID for tracking."""
        import uuid
        return str(uuid.uuid4())

    def _get_vecteezy_specific_headers(self) -> Dict[str, str]:
        """Get headers specifically designed for Vecteezy.com."""
        vecteezy_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "DNT": "1",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.google.com/",
            "Origin": "https://www.vecteezy.com",
            "Host": "www.vecteezy.com"
        }
        return vecteezy_headers

    def _get_rotating_user_agent(self) -> str:
        """Get a rotating user agent with more variety."""
        user_agents = [
            # Chrome variants
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            # Firefox variants
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
            # Edge variants
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/119.0.0.0",
            # Safari variants
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        ]
        import random
        return random.choice(user_agents)

    def set_retry_strategy(self, strategy: str = "exponential") -> None:
        """Set retry strategy for failed requests."""
        self.retry_strategy = strategy

    async def _apply_retry_strategy(self, attempt: int, base_delay: float) -> float:
        """Apply the configured retry strategy."""
        if hasattr(self, 'retry_strategy'):
            if self.retry_strategy == "exponential":
                return base_delay * (2 ** attempt)
            elif self.retry_strategy == "linear":
                return base_delay * (attempt + 1)
            elif self.retry_strategy == "random":
                import random
                return random.uniform(base_delay, base_delay * 3)
        return base_delay * (attempt + 1)

    def set_url_patterns(self, patterns: List[str]) -> None:
        """Set custom URL extraction patterns."""
        self.url_patterns = patterns

    def set_extraction_patterns(self, patterns: List[str]) -> None:
        """Set custom extraction patterns for URL parameters."""
        self.extraction_patterns = patterns

    def set_default_headers(self, headers: Dict[str, str]) -> None:
        """Set custom default headers."""
        self.default_headers.update(headers)

    @staticmethod
    def _unescape_json_url(url: str) -> str:
        """Unescape common JSON-escaped sequences found in HTML data."""
        return (
            url.replace("\\/", "/")
               .replace("\\u0026", "&")
               .replace("&amp;", "&")
               .replace("\\u0027", "'")
               .replace("\\u0022", '"')
        )

    def _extract_urls_from_html(self, html: str) -> List[str]:
        """Extract image URLs from HTML using configured patterns."""
        urls_set: Set[str] = set()

        # Extract URLs using configured patterns
        for pattern in self.url_patterns:
            try:
                matches = re.findall(pattern, html)
                for match in matches:
                    if isinstance(match, tuple):
                        # Handle capture groups
                        for group in match:
                            if group.startswith("http"):
                                urls_set.add(self._unescape_json_url(group))
                    elif isinstance(match, str) and match.startswith("http"):
                        urls_set.add(self._unescape_json_url(match))
            except Exception as e:
                logger.warning(f"Error processing pattern {pattern}: {e}")

        self.stats["found_urls"] = len(urls_set)

        # Normalize: resolve wrapper URLs in query strings
        normalized: Set[str] = set()
        for url in urls_set:
            try:
                if any(pattern in url for pattern in self.extraction_patterns):
                    parsed = urlparse(url)
                    qs = parse_qs(parsed.query)
                    for key in self.extraction_patterns:
                        key_clean = key.rstrip("=")
                        vals = qs.get(key_clean)
                        if vals and vals[0].startswith("http"):
                            normalized.add(self._unescape_json_url(vals[0]))
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
                "/search",
                "/th?id=",
                "/rp/",
                "/fd/ls/",
                "/hp/",
                "/ck/a",
                "/aclick",
                "/favicon",
                "/policies/",
                "/logo",
                "javascript:",
                "mailto:",
                "tel:",
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
        """Check content type of URL using HEAD request or GET with Range header."""
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
        """Infer file extension from content type."""
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
            "image/avif": "avif",
        }
        for key, ext in mapping.items():
            if content_type.lower().startswith(key):
                return ext
        return None

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize filename for safe file system usage."""
        cleaned = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_", "."))
        return cleaned.replace(" ", "_")

    def _generate_filename(self, url: str, query: str, content_type: Optional[str]) -> str:
        """Generate unique filename for downloaded image."""
        ext = self._infer_extension_from_content_type(content_type) or "jpg"
        query_slug = self._sanitize_filename(query.strip().replace(" ", "_")) or "query"
        ts_ns = time.time_ns()
        h = hashlib.sha1(str(ts_ns).encode()).hexdigest()[:12]
        return f"{query_slug}_{h}.{ext}"

    def _check_image_exists(self, image_url: str) -> bool:
        """Check if image URL already exists in database."""
        try:
            if not self.image_service:
                return False
            return self.image_service.get_image_resource_by_url(image_url) is not None
        except Exception as e:
            logger.error(f"Error checking existing URL: {e}")
            return False

    def _save_image_record(
        self,
        image_url: str,
        filename: str,
        query: str,
        content_type: Optional[str],
        source_url: Optional[str] = None,
    ) -> Optional[str]:
        """Save image record to database."""
        try:
            if not self.image_service:
                return None
            ext = self._infer_extension_from_content_type(content_type)
            image_data = ImageResourceCreate(
                url=image_url,
                filename=filename,
                file_path=str(self.resource_dir / filename),
                source=self.source_name,
                search_query=query,
                tags=[query] if query else None,
                format=ext,
                metadata={"source_url": source_url} if source_url else None,
            )
            saved = self.image_service.create_image_resource(image_data)
            self.stats["saved_records"] += 1
            return saved.id
        except Exception as e:
            logger.error(f"Error saving DB record: {e}")
            self.stats["errors"] += 1
            return None

    async def _download_image(self, url: str, filename: str) -> bool:
        """Download image from URL and save to local storage."""
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

    async def crawl(
        self,
        url: str,
        query: str = "",
        max_links: int = 50,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        delay: float = 0.25,
    ) -> Dict[str, Any]:
        """Main crawling method for any HTML source."""
        self.stats["start_time"] = datetime.utcnow().isoformat()

        html = await self.fetch_html(url, headers, params, method, data)
        if not html:
            return {
                "success": False,
                "reason": "failed_to_fetch_html",
                "source_url": url,
                "stats": self.stats
            }

        urls = self._extract_urls_from_html(html)
        self.stats["image_candidates"] = len(urls)

        saved = 0
        downloaded = 0

        for url_item in urls[:max_links]:
            try:
                if self._check_image_exists(url_item):
                    continue

                content_type = await self._head_content_type(url_item)
                if not content_type or not content_type.lower().startswith("image/"):
                    continue

                filename = self._generate_filename(url_item, query, content_type)
                image_id = self._save_image_record(url_item, filename, query, content_type, url)

                if image_id:
                    saved += 1
                    ok = await self._download_image(url_item, filename)
                    if ok and self.image_service:
                        downloaded += 1
                        self.image_service.update_download_status(image_id, "completed")
                    elif self.image_service:
                        self.image_service.update_download_status(image_id, "failed", "Download failed")

                if delay > 0:
                    await self._human_delay()
            except Exception as e:
                logger.error(f"Error processing {url_item}: {e}")
                self.stats["errors"] += 1

        return {
            "success": True,
            "source_url": url,
            "query": query,
            "saved": saved,
            "downloaded": downloaded,
            "stats": self.stats,
        }

    async def crawl_multiple_sources(
        self,
        sources: List[Dict[str, Any]],
        max_links_per_source: int = 50,
        delay_between_sources: float = 1.0,
    ) -> Dict[str, Any]:
        """Crawl multiple sources with different configurations."""
        all_results = []
        total_stats = {
            "start_time": datetime.utcnow().isoformat(),
            "sources_processed": 0,
            "total_saved": 0,
            "total_downloaded": 0,
            "total_errors": 0,
        }

        for source_config in sources:
            try:
                result = await self.crawl(
                    url=source_config["url"],
                    query=source_config.get("query", ""),
                    max_links=max_links_per_source,
                    headers=source_config.get("headers"),
                    params=source_config.get("params"),
                    method=source_config.get("method", "GET"),
                    data=source_config.get("data"),
                    delay=source_config.get("delay", 0.25),
                )
                
                all_results.append(result)
                if result["success"]:
                    total_stats["sources_processed"] += 1
                    total_stats["total_saved"] += result["saved"]
                    total_stats["total_downloaded"] += result["downloaded"]
                    total_stats["total_errors"] += result["stats"]["errors"]

                if delay_between_sources > 0:
                    await asyncio.sleep(delay_between_sources)

            except Exception as e:
                logger.error(f"Error processing source {source_config.get('url', 'unknown')}: {e}")
                total_stats["total_errors"] += 1

        return {
            "success": True,
            "results": all_results,
            "total_stats": total_stats,
        }