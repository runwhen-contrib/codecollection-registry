"""
Web crawler for fetching documentation content from URLs.

Uses crawl4ai (headless browser) as primary crawler for rich markdown output.
Falls back to httpx + BeautifulSoup for environments where crawl4ai isn't available.
"""
import asyncio
import logging
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Try to import crawl4ai (primary - headless browser, clean markdown output)
HAS_CRAWL4AI = False
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    HAS_CRAWL4AI = True
    logger.info("crawl4ai available - using headless browser for documentation crawling")
except ImportError:
    logger.info("crawl4ai not installed, checking fallback options...")

# Fallback: httpx + BeautifulSoup
HAS_BS4 = False
try:
    from bs4 import BeautifulSoup
    import httpx
    HAS_BS4 = True
    if not HAS_CRAWL4AI:
        logger.info("Using httpx + BeautifulSoup fallback for web crawling")
except ImportError:
    if not HAS_CRAWL4AI:
        logger.warning("No web crawling available. Install crawl4ai or beautifulsoup4.")


class Crawl4AICrawler:
    """
    Primary crawler using crawl4ai (headless Chromium browser).
    
    Advantages over simple HTTP + BeautifulSoup:
    - Renders JavaScript (handles SPAs, Confluence Scroll Viewport, etc.)
    - Outputs clean markdown (preserves headings, lists, code blocks)
    - Better content extraction (removes nav, footer, sidebar automatically)
    - LLM-ready output format
    """

    def __init__(self, timeout: float = 30.0, max_content_length: int = 50000):
        self.timeout = timeout
        self.max_content_length = max_content_length

    def crawl_url(self, url: str) -> Optional[Dict[str, str]]:
        """Crawl a single URL and return structured content with clean markdown."""
        logger.info(f"Crawling (crawl4ai): {url}")
        try:
            return asyncio.run(self._async_crawl(url))
        except RuntimeError:
            # Already inside an event loop (e.g., called from async context)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(self._async_crawl(url))).result(timeout=self.timeout + 10)
            raise

    async def _async_crawl(self, url: str) -> Optional[Dict[str, str]]:
        """Async crawl implementation."""
        browser_cfg = BrowserConfig(
            headless=True,
            verbose=False,
        )
        run_cfg = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10,  # Skip very short blocks
        )

        try:
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                result = await crawler.arun(url=url, config=run_cfg)

                if not result.success:
                    logger.warning(f"crawl4ai failed for {url}: {result.error_message}")
                    return None

                # result.markdown contains clean, structured markdown
                markdown_content = result.markdown or ""
                if not markdown_content.strip():
                    logger.warning(f"No content extracted from {url}")
                    return None

                # Truncate if needed
                if len(markdown_content) > self.max_content_length:
                    markdown_content = markdown_content[:self.max_content_length] + "\n\n... (truncated)"

                # Extract headings from the markdown
                headings = []
                for match in re.finditer(r'^(#{1,4})\s+(.+)$', markdown_content, re.MULTILINE):
                    level = len(match.group(1))
                    headings.append({'level': level, 'text': match.group(2).strip()})

                # Extract code blocks
                code_blocks = re.findall(r'```[\w]*\n(.*?)```', markdown_content, re.DOTALL)

                # Extract title (first h1 or page title)
                title = ""
                if headings:
                    title = headings[0]['text']

                content_length = len(markdown_content)
                logger.info(f"  Extracted {content_length} chars, {len(headings)} headings, {len(code_blocks)} code blocks")

                return {
                    'title': title,
                    'content': markdown_content,  # Clean markdown, not raw text blob
                    'code_blocks': code_blocks[:10],
                    'headings': headings,
                    'url': url,
                    'crawler': 'crawl4ai'
                }

        except Exception as e:
            logger.error(f"crawl4ai error for {url}: {e}")
            return None


class BS4Crawler:
    """
    Fallback crawler using httpx + BeautifulSoup.
    
    Simpler but limited:
    - No JavaScript rendering
    - Basic text extraction (loses structure)
    - Manual content area detection
    """

    def __init__(self, timeout: float = 30.0, max_content_length: int = 50000, rate_limit_delay: float = 1.0):
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def crawl_url(self, url: str) -> Optional[Dict[str, str]]:
        """Crawl a single URL using httpx + BeautifulSoup."""
        logger.info(f"Crawling (bs4 fallback): {url}")
        self._rate_limit()

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers={
                    'User-Agent': 'RunWhen-MCP-Indexer/1.0 (Documentation Indexer)'
                })
                response.raise_for_status()
                html = response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

        return self._extract_content(html, url)

    def _extract_content(self, html: str, url: str) -> Optional[Dict[str, str]]:
        """Extract structured content from HTML."""
        soup = BeautifulSoup(html, 'lxml')

        # Remove non-content elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()

        # Find main content area
        main_content = None
        selectors = [
            'article', 'main', '.content', '.article-content',
            '#content', '#main-content', '.scroll-content',
            '.confluence-information-macro-body',
        ]
        for selector in selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        if not main_content:
            main_content = soup.body or soup

        # Title
        title = ""
        title_elem = soup.find('h1') or soup.find('title')
        if title_elem:
            title = title_elem.get_text(strip=True)

        # Headings
        headings = []
        for h in main_content.find_all(['h1', 'h2', 'h3', 'h4']):
            text = h.get_text(strip=True)
            if text:
                headings.append({'level': int(h.name[1]), 'text': text})

        # Code blocks
        code_blocks = []
        for code in main_content.find_all(['code', 'pre']):
            code_text = code.get_text(strip=True)
            if code_text and len(code_text) > 10:
                code_blocks.append(code_text[:2000])

        # Main text
        text = main_content.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        if len(text) > self.max_content_length:
            text = text[:self.max_content_length] + "..."

        if not text.strip():
            return None

        logger.info(f"  Extracted {len(text)} chars, {len(headings)} headings")

        return {
            'title': title,
            'content': text,
            'code_blocks': code_blocks[:10],
            'headings': headings,
            'url': url,
            'crawler': 'bs4'
        }


class WebCrawler:
    """
    Unified web crawler interface.
    
    Uses crawl4ai (headless browser) when available for rich markdown output.
    Falls back to httpx + BeautifulSoup for simpler environments.
    Auto-degrades: if crawl4ai fails (e.g. missing browser deps), switches to bs4.
    """

    def __init__(self, timeout: float = 30.0, max_content_length: int = 50000, rate_limit_delay: float = 1.0):
        self._timeout = timeout
        self._max_content_length = max_content_length
        self._rate_limit_delay = rate_limit_delay
        self._crawl4ai_failed = False  # Track if crawl4ai runtime is broken
        
        if HAS_CRAWL4AI:
            self._primary = Crawl4AICrawler(timeout=timeout, max_content_length=max_content_length)
        else:
            self._primary = None
        
        if HAS_BS4:
            self._fallback = BS4Crawler(timeout=timeout, max_content_length=max_content_length, rate_limit_delay=rate_limit_delay)
        else:
            self._fallback = None
        
        self._backend = "crawl4ai" if self._primary else ("bs4" if self._fallback else "none")

    def is_available(self) -> bool:
        return self._primary is not None or self._fallback is not None

    @property
    def backend(self) -> str:
        return self._backend

    def crawl_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        Crawl a URL using the best available backend.
        
        Auto-degrades: if crawl4ai fails on first attempt (runtime issue like
        missing browser deps), switches to bs4 for all subsequent calls.
        """
        # Try crawl4ai first (unless it already failed)
        if self._primary and not self._crawl4ai_failed:
            try:
                result = self._primary.crawl_url(url)
                if result:
                    self._crawl4ai_consecutive_failures = 0
                    return result
                # crawl4ai returned None -- count as failure
                self._crawl4ai_consecutive_failures = getattr(self, '_crawl4ai_consecutive_failures', 0) + 1
                if self._crawl4ai_consecutive_failures >= 2:
                    logger.warning("crawl4ai failed twice consecutively, disabling for remaining URLs")
                    self._crawl4ai_failed = True
                    self._backend = "bs4 (crawl4ai degraded)"
                else:
                    logger.info(f"crawl4ai returned no content for {url}, trying bs4 fallback")
            except Exception as e:
                # crawl4ai runtime failure (missing libs, browser crash, etc.)
                logger.warning(f"crawl4ai runtime failure: {e}")
                logger.warning("Disabling crawl4ai, switching to bs4 for remaining URLs")
                self._crawl4ai_failed = True
                self._backend = "bs4 (crawl4ai degraded)"
        
        # Fallback to bs4
        if self._fallback:
            try:
                return self._fallback.crawl_url(url)
            except Exception as e:
                logger.error(f"bs4 fallback also failed for {url}: {e}")
                return None
        
        logger.warning("No web crawling backend available")
        return None

    def crawl_urls(self, urls: List[str]) -> List[Dict[str, str]]:
        """Crawl multiple URLs."""
        results = []
        for url in urls:
            content = self.crawl_url(url)
            if content:
                results.append(content)
        return results


def create_doc_text_from_crawled(crawled: Dict[str, str]) -> str:
    """
    Create a text document suitable for embedding from crawled content.
    
    If content is already markdown (from crawl4ai), use it directly.
    If content is raw text (from bs4), add structure from headings.
    """
    parts = []

    if crawled.get('title'):
        parts.append(f"Title: {crawled['title']}")

    if crawled.get('headings'):
        heading_text = " > ".join([h['text'] for h in crawled['headings'][:10]])
        parts.append(f"Sections: {heading_text}")

    # Main content (markdown from crawl4ai or text from bs4)
    if crawled.get('content'):
        content = crawled['content'][:10000]
        parts.append(content)

    if crawled.get('code_blocks'):
        code_text = "\n".join(crawled['code_blocks'][:5])[:3000]
        parts.append(f"Code examples: {code_text}")

    return " ".join(parts)
