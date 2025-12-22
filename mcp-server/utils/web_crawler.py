"""
Web crawler for fetching documentation content from URLs.

Supports Confluence/Scroll Viewport rendered pages and general HTML.
"""
import logging
import re
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

# Try to import BeautifulSoup
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    logger.warning("beautifulsoup4 not installed. Web crawling disabled.")


class WebCrawler:
    """
    Crawl documentation websites and extract content.
    
    Optimized for:
    - Confluence/Scroll Viewport pages (docs.runwhen.com)
    - General HTML documentation sites
    """
    
    def __init__(
        self,
        timeout: float = 30.0,
        max_content_length: int = 50000,
        rate_limit_delay: float = 1.0
    ):
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0
        
    def is_available(self) -> bool:
        """Check if web crawling is available"""
        return HAS_BS4
    
    def _rate_limit(self):
        """Apply rate limiting between requests"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()
    
    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from a URL.
        
        Returns:
            HTML content or None if failed
        """
        if not HAS_BS4:
            return None
            
        self._rate_limit()
        
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers={
                    'User-Agent': 'RunWhen-MCP-Indexer/1.0 (Documentation Indexer)'
                })
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def extract_content(self, html: str, url: str = "") -> Dict[str, str]:
        """
        Extract structured content from HTML.
        
        Returns:
            Dict with 'title', 'content', 'code_blocks', 'headings'
        """
        if not HAS_BS4:
            return {}
            
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Try to find the main content area
        # Confluence/Scroll Viewport typically uses these selectors
        main_content = None
        selectors = [
            'article',
            'main',
            '.content',
            '.article-content',
            '#content',
            '#main-content',
            '.scroll-content',  # Scroll Viewport
            '.confluence-information-macro-body',
        ]
        
        for selector in selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.body or soup
        
        # Extract title
        title = ""
        title_elem = soup.find('h1') or soup.find('title')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # Extract headings for structure
        headings = []
        for h in main_content.find_all(['h1', 'h2', 'h3', 'h4']):
            text = h.get_text(strip=True)
            if text:
                level = int(h.name[1])
                headings.append({'level': level, 'text': text})
        
        # Extract code blocks separately (valuable for technical docs)
        code_blocks = []
        for code in main_content.find_all(['code', 'pre']):
            code_text = code.get_text(strip=True)
            if code_text and len(code_text) > 10:  # Skip tiny inline code
                code_blocks.append(code_text[:2000])  # Limit code block size
        
        # Extract main text content
        # Clean up the text
        text = main_content.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Truncate if too long
        if len(text) > self.max_content_length:
            text = text[:self.max_content_length] + "..."
        
        return {
            'title': title,
            'content': text,
            'code_blocks': code_blocks[:10],  # Limit to 10 code blocks
            'headings': headings,
            'url': url
        }
    
    def crawl_url(self, url: str) -> Optional[Dict[str, str]]:
        """
        Crawl a single URL and extract content.
        
        Returns:
            Dict with extracted content or None if failed
        """
        logger.info(f"Crawling: {url}")
        
        html = self.fetch_page(url)
        if not html:
            return None
        
        content = self.extract_content(html, url)
        
        if content.get('content'):
            logger.info(f"  Extracted {len(content['content'])} chars, {len(content.get('headings', []))} headings")
            return content
        
        return None
    
    def crawl_urls(self, urls: List[str]) -> List[Dict[str, str]]:
        """
        Crawl multiple URLs and extract content.
        
        Returns:
            List of extracted content dicts
        """
        results = []
        
        for url in urls:
            content = self.crawl_url(url)
            if content:
                results.append(content)
        
        return results


def create_doc_text_from_crawled(crawled: Dict[str, str]) -> str:
    """
    Create a text document suitable for embedding from crawled content.
    
    Combines title, headings, content, and code blocks into a searchable format.
    """
    parts = []
    
    # Add title
    if crawled.get('title'):
        parts.append(f"Title: {crawled['title']}")
    
    # Add headings as structure
    if crawled.get('headings'):
        heading_text = " > ".join([h['text'] for h in crawled['headings'][:10]])
        parts.append(f"Sections: {heading_text}")
    
    # Add main content (most important for semantic search)
    if crawled.get('content'):
        # Take first ~10k chars for embedding
        content = crawled['content'][:10000]
        parts.append(content)
    
    # Add code examples (often what users search for)
    if crawled.get('code_blocks'):
        code_text = "\n".join(crawled['code_blocks'][:5])[:3000]
        parts.append(f"Code examples: {code_text}")
    
    return " ".join(parts)


