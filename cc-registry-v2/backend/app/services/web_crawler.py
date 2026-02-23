"""
Lightweight web crawler for documentation indexing.

Fetches page content with httpx + BeautifulSoup. Runs inside the backend
worker, so no headless-browser dependency is needed.
"""
import logging
import re
import time
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TIMEOUT = 30.0
MAX_CONTENT_LENGTH = 50_000
RATE_LIMIT_DELAY = 1.0
USER_AGENT = "RunWhen-Registry-Indexer/2.0 (Documentation Indexer)"


class WebCrawler:
    def __init__(
        self,
        timeout: float = TIMEOUT,
        max_content_length: int = MAX_CONTENT_LENGTH,
        rate_limit_delay: float = RATE_LIMIT_DELAY,
    ):
        self._timeout = timeout
        self._max_content_length = max_content_length
        self._rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def crawl_url(self, url: str) -> Optional[Dict[str, str]]:
        """Fetch a URL and extract structured content."""
        logger.info(f"Crawling: {url}")
        self._rate_limit()

        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": USER_AGENT})
                resp.raise_for_status()
                html = resp.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

        return self._extract(html, url)

    def crawl_urls(self, urls: List[str]) -> List[Dict[str, str]]:
        results = []
        for url in urls:
            content = self.crawl_url(url)
            if content:
                results.append(content)
        return results

    def _extract(self, html: str, url: str) -> Optional[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        main = None
        for sel in (
            "article", "main", ".content", ".article-content",
            "#content", "#main-content", ".scroll-content",
        ):
            main = soup.select_one(sel)
            if main:
                break
        if not main:
            main = soup.body or soup

        title = ""
        title_el = soup.find("h1") or soup.find("title")
        if title_el:
            title = title_el.get_text(strip=True)

        headings = []
        for h in main.find_all(["h1", "h2", "h3", "h4"]):
            txt = h.get_text(strip=True)
            if txt:
                headings.append({"level": int(h.name[1]), "text": txt})

        code_blocks = []
        for code in main.find_all(["code", "pre"]):
            code_text = code.get_text(strip=True)
            if code_text and len(code_text) > 10:
                code_blocks.append(code_text[:2000])

        text = main.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        if len(text) > self._max_content_length:
            text = text[: self._max_content_length] + "..."

        if not text.strip():
            return None

        logger.info(f"  Extracted {len(text)} chars, {len(headings)} headings")
        return {
            "title": title,
            "content": text,
            "code_blocks": code_blocks[:10],
            "headings": headings,
            "url": url,
        }
