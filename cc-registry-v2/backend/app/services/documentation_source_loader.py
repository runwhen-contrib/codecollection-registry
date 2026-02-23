"""
Load documentation sources from sources.yaml and crawl their content.

This replaces the MCP server's standalone indexer for documentation.
The same sources.yaml is used — it is mounted into the backend container.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.services.web_crawler import WebCrawler

logger = logging.getLogger(__name__)

SOURCES_PATHS = [
    Path("/app/sources.yaml"),
    Path("/workspaces/codecollection-registry/mcp-server/sources.yaml"),
]


def _find_sources_file() -> Optional[Path]:
    for p in SOURCES_PATHS:
        if p.exists():
            return p
    return None


class DocumentationSourceLoader:
    """Parse sources.yaml and optionally crawl linked pages."""

    def __init__(self, sources_file: Optional[str] = None):
        if sources_file:
            self._path = Path(sources_file)
        else:
            self._path = _find_sources_file()
        self._raw: Optional[Dict] = None

    def _load(self):
        if self._raw is not None:
            return
        if not self._path or not self._path.exists():
            logger.warning(f"sources.yaml not found (tried {SOURCES_PATHS})")
            self._raw = {}
            return
        with open(self._path) as f:
            self._raw = yaml.safe_load(f) or {}
        logger.info(f"Loaded sources from {self._path}")

    def get_all_docs(self, crawl: bool = True) -> List[Dict[str, Any]]:
        """Return a flat list of documentation entries, optionally with crawled content.

        Each dict contains at minimum: name, url, description, category, topics.
        If *crawl* is True, the ``crawled_content`` key is populated from the URL.
        """
        self._load()
        sources = self._raw.get("sources", {})
        docs: List[Dict[str, Any]] = []

        for category, items in sources.items():
            if not isinstance(items, list):
                continue
            for item in items:
                entry: Dict[str, Any] = {}

                if "name" in item:
                    entry["name"] = item["name"]
                    entry["url"] = item.get("url", "")
                    entry["description"] = item.get("description", "")
                    entry["topics"] = item.get("topics", [])
                    entry["usage_examples"] = item.get("usage_examples", [])
                    entry["key_points"] = item.get("key_points", [])
                    entry["priority"] = item.get("priority", "medium")
                elif "question" in item:
                    entry["name"] = item["question"]
                    entry["url"] = ""
                    entry["description"] = item.get("answer", "")
                    entry["topics"] = item.get("topics", [])
                else:
                    continue

                entry["category"] = category
                docs.append(entry)

        if crawl:
            self._crawl_docs(docs)

        logger.info(f"Loaded {len(docs)} documentation entries ({sum(1 for d in docs if d.get('crawled_content'))} crawled)")
        return docs

    @staticmethod
    def _crawl_docs(docs: List[Dict[str, Any]]):
        crawler = WebCrawler()
        for doc in docs:
            url = doc.get("url")
            if not url:
                continue
            result = crawler.crawl_url(url)
            if result:
                doc["crawled_content"] = result.get("content", "")
                doc["crawled_headings"] = [
                    h["text"] for h in result.get("headings", [])
                ]
                doc["crawled_code"] = result.get("code_blocks", [])
