"""
Documentation Tools

Tools for finding documentation, guides, and development resources.
Primary path: semantic search via the backend's vector search API.
Fallback: local docs.yaml keyword matching (for offline/disconnected use).
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .base import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


# =============================================================================
# Local docs.yaml fallback (used only when backend vector search is unavailable)
# =============================================================================

@dataclass
class DocEntry:
    """A documentation entry"""
    name: str
    url: str
    description: str
    keywords: List[str]
    category: str
    examples: Optional[List[str]] = None


class DocumentationManager:
    """Keyword-match search over local docs.yaml — fallback only."""

    def __init__(self, docs_file: str = None):
        if docs_file is None:
            docs_file = Path(__file__).parent.parent / "docs.yaml"
        self.docs_file = Path(docs_file)
        self._docs: Optional[Dict] = None
        self._entries: List[DocEntry] = []

    def _load(self) -> None:
        if self._docs is not None:
            return
        if not self.docs_file.exists():
            logger.warning(f"docs.yaml not found at {self.docs_file}")
            self._docs = {}
            return
        try:
            with open(self.docs_file, 'r') as f:
                self._docs = yaml.safe_load(f) or {}
            docs = self._docs.get("documentation", {})
            for category, items in docs.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if "name" in item:
                        self._entries.append(DocEntry(
                            name=item.get("name", ""),
                            url=item.get("url", ""),
                            description=item.get("description", ""),
                            keywords=item.get("keywords", []),
                            category=category,
                            examples=item.get("examples"),
                        ))
                    elif "question" in item:
                        self._entries.append(DocEntry(
                            name=item.get("question", ""),
                            url="",
                            description=item.get("answer", ""),
                            keywords=item.get("keywords", []),
                            category="faq",
                        ))
        except Exception as e:
            logger.error(f"Failed to load docs.yaml: {e}")
            self._docs = {}

    def search(self, query: str, category: str = None, limit: int = 5) -> List[DocEntry]:
        self._load()
        query_lower = query.lower()
        query_words = set(query_lower.split())
        scored = []
        for entry in self._entries:
            if category and entry.category != category:
                continue
            score = 0
            if query_lower in entry.name.lower():
                score += 5
            for kw in entry.keywords:
                if kw.lower() in query_lower or query_lower in kw.lower():
                    score += 3
            if query_lower in entry.description.lower():
                score += 2
            all_text = f"{entry.name} {entry.description} {' '.join(entry.keywords)}".lower()
            for word in query_words:
                if word in all_text:
                    score += 0.5
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def get_by_category(self, category: str) -> List[DocEntry]:
        self._load()
        return [e for e in self._entries if e.category == category]

    def list_categories(self) -> List[str]:
        self._load()
        return list(set(e.category for e in self._entries))

    def get_all_urls(self) -> Dict[str, str]:
        self._load()
        return {e.name: e.url for e in self._entries if e.url}


_doc_manager: Optional[DocumentationManager] = None


def get_doc_manager() -> DocumentationManager:
    global _doc_manager
    if _doc_manager is None:
        _doc_manager = DocumentationManager()
    return _doc_manager


# =============================================================================
# Documentation Tools
# =============================================================================

class FindDocumentationTool(BaseTool):
    """
    Find documentation, guides, and FAQs.

    Primary: semantic vector search via backend API (/api/v1/vector/search/documentation).
    Fallback: keyword matching on local docs.yaml.
    """

    def __init__(self, registry_client=None):
        self._client = registry_client

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_documentation",
            description="Find documentation, guides, examples, and FAQs for CodeBundle development. Ask how-to questions or search for specific topics.",
            category="search",
            parameters=[
                ToolParameter(name="query", type="string", description="What documentation to find", required=True),
                ToolParameter(name="category", type="string", description="Documentation category filter", required=False, default="all",
                              enum=["codebundle_development", "libraries", "platform", "faq", "all"]),
                ToolParameter(name="max_results", type="integer", description="Maximum results", required=False, default=10),
            ],
        )

    async def execute(self, query: str, category: str = "all", max_results: int = 10) -> str:
        # Try backend vector search first
        if self._client:
            try:
                cat = category if category != "all" else None
                results = await self._client.vector_search_documentation(
                    query=query, max_results=max_results, category=cat,
                )
                if results:
                    return self._format_vector_results(query, results)
                logger.info("Backend vector search returned no results, falling back to keyword search")
            except Exception as e:
                logger.warning(f"Backend vector search unavailable ({e}), falling back to keyword search")

        return self._keyword_search(query, category, max_results)

    def _keyword_search(self, query: str, category: str, max_results: int) -> str:
        doc_manager = get_doc_manager()
        results = doc_manager.search(
            query=query,
            category=category if category != "all" else None,
            limit=max_results,
        )
        if not results:
            return f"No documentation found matching: {query}\n\nCheck the official RunWhen documentation at https://docs.runwhen.com"

        output = f"# Documentation: {query}\n\nFound {len(results)} resource(s):\n\n"
        for entry in results:
            output += f"## **{entry.name}**\n\n"
            output += f"**Category:** {entry.category}\n\n"
            if entry.description:
                output += f"**Description:** {entry.description}\n\n"
            if entry.url:
                output += f"**Link:** [{entry.url}]({entry.url})\n\n"
            if entry.examples:
                output += "**Examples:**\n"
                for ex in entry.examples[:2]:
                    output += f"```robot\n{ex}\n```\n\n"
            output += "---\n\n"
        return output

    @staticmethod
    def _format_vector_results(query: str, results: List[Dict[str, Any]]) -> str:
        output = f"# Documentation: {query}\n\nFound {len(results)} result(s) (semantic search):\n\n"
        for r in results:
            meta = r.get("metadata", {})
            name = meta.get("name", r.get("id", ""))
            output += f"## **{name}**\n\n"
            if meta.get("category"):
                output += f"**Category:** {meta['category']}\n\n"
            desc = meta.get("description", "")
            if desc:
                output += f"**Description:** {desc}\n\n"
            url = meta.get("url", "")
            if url:
                output += f"**Link:** [{url}]({url})\n\n"
            score = r.get("score", 0)
            output += f"**Relevance:** {score:.2%}\n\n---\n\n"
        return output


class GetDevelopmentRequirementsTool(BaseTool):
    """Get development requirements and best practices."""

    def __init__(self, registry_client=None):
        self._client = registry_client

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_development_requirements",
            description="Get development requirements, best practices, and documentation for specific features",
            category="info",
            parameters=[
                ToolParameter(name="feature", type="string", description="Feature to get requirements for (e.g., 'secrets', 'tasks', 'slis')", required=True),
            ],
        )

    async def execute(self, feature: str) -> str:
        # Try backend vector search first
        if self._client:
            try:
                results = await self._client.vector_search_documentation(
                    query=feature, max_results=3,
                )
                if results:
                    return FindDocumentationTool._format_vector_results(feature, results)
            except Exception:
                pass

        doc_manager = get_doc_manager()
        results = doc_manager.search(feature, limit=3)
        output = f"# Development Requirements: {feature}\n\n"
        if results:
            for entry in results:
                output += f"## **{entry.name}**\n\n"
                if entry.description:
                    output += f"{entry.description}\n\n"
                if entry.url:
                    output += f"**Documentation:** [{entry.url}]({entry.url})\n\n"
                if entry.examples:
                    output += "**Examples:**\n"
                    for ex in entry.examples:
                        output += f"```robot\n{ex}\n```\n\n"
                output += "---\n\n"
        else:
            output += f"No specific documentation found for '{feature}'.\n\n"
            output += "Check the official RunWhen documentation at https://docs.runwhen.com/public/runwhen-authors\n"
        return output
