"""
Skill registry helpers (internal class names preserved for backward compatibility).

Task helpers for finding, listing, and getting details about Skills
(internally still called ``CodeBundle`` everywhere — see Phase 1 cosmetic
rename notes in ``mcp-server/utils/terminology.py``). All data is fetched
from the Registry API.
"""
import json
import logging
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# Common stop words stripped from NL queries before sending to the backend
_STOP_WORDS = frozenset({
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
    'am', 'do', 'does', 'did', 'have', 'has', 'had', 'having',
    'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she',
    'it', 'its', 'they', 'them', 'their', 'there', 'here',
    'and', 'or', 'but', 'if', 'so', 'yet', 'nor', 'not', 'no',
    'at', 'by', 'for', 'from', 'in', 'into', 'of', 'on', 'to',
    'up', 'out', 'off', 'with', 'as', 'than', 'too', 'very',
    'how', 'what', 'when', 'where', 'why', 'which', 'who',
    'whom', 'this', 'that', 'these', 'those', 'can', 'could',
    'will', 'would', 'shall', 'should', 'may', 'might',
    'about', 'over', 'just', 'also', 'some', 'any', 'all',
    "isn't", "aren't", "don't", "doesn't", "didn't", "won't",
})


def _extract_search_keywords(query: str) -> str:
    """
    Extract meaningful keywords from a natural language query.
    
    Strips stop words and punctuation so the backend text search
    receives only content-bearing terms.
    
    Examples:
        "How do I scale out my Azure App Service when traffic spikes?"
        → "scale Azure App Service traffic spikes"
    """
    raw = [w.strip('?.,!:;()[]"\' ') for w in query.split()]
    keywords = [w for w in raw if len(w) >= 2 and w.lower() not in _STOP_WORDS]
    if not keywords:
        # Nothing survived filtering — keep the longest raw words
        keywords = sorted(raw, key=len, reverse=True)[:4]
    return ' '.join(keywords[:8])


class FindCodeBundleTool(BaseTool):
    """
    Search to find Skills (formerly "CodeBundles") matching
    natural language queries. Delegates search to the Registry API.
    """
    
    def __init__(self, registry_client):
        self._client = registry_client
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_codebundle",
            description="Find Skills (formerly 'CodeBundles') for your use case. A Skill is a reusable package of Tasks — Runbooks that run on demand and Monitors that run on a schedule. Describe what you need in natural language. Examples: 'troubleshoot Kubernetes pods', 'monitor AWS EKS', 'check database health'.",
            category="search",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Natural language description of what you're looking for",
                    required=True
                ),
                ToolParameter(
                    name="platform",
                    type="string",
                    description="Optional platform filter",
                    required=False,
                    enum=["Kubernetes", "AWS", "Azure", "GCP", "Linux", "Database"]
                ),
                ToolParameter(
                    name="collection",
                    type="string",
                    description="Optional collection filter",
                    required=False
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum results to return",
                    required=False,
                    default=10
                )
            ]
        )
    
    async def execute(
        self,
        query: str,
        platform: Optional[str] = None,
        collection: Optional[str] = None,
        max_results: int = 10
    ) -> str:
        """Find codebundles via the Registry API."""
        # Extract keywords from the natural language query so the
        # backend text search has clean terms to work with.
        search_terms = _extract_search_keywords(query)
        logger.info(f"find_codebundle: query={query!r} → search_terms={search_terms!r}")
        
        try:
            results = await self._client.search_codebundles(
                search=search_terms,
                platform=platform,
                collection_slug=collection,
                max_results=max_results,
            )
        except Exception as e:
            logger.error(f"Registry API search failed: {e}")
            return f"Search unavailable: {e}"
        
        if not results:
            # Retry without platform filter — some codebundles have
            # a mismatched or null discovery_platform
            if platform:
                try:
                    results = await self._client.search_codebundles(
                        search=search_terms,
                        collection_slug=collection,
                        max_results=max_results,
                    )
                except Exception:
                    pass
        
        if not results:
            return f"No Skills found matching: {query}\n\nTry rephrasing your query or using broader terms."
        
        # Compute relevance scores.  The backend already sorts by weighted
        # field relevance, so we use position-based scoring that preserves
        # that order, plus a name-match check to penalise results that don't
        # contain any search keyword in their name/slug/tags (i.e. they only
        # matched via a long description field).
        search_kws = [w.lower() for w in search_terms.split() if len(w) >= 2]
        
        output = f"# Skills for: {query}\n\n"
        output += f"Found {len(results)} matching Skill(s):\n\n"
        
        for i, cb in enumerate(results, 1):
            display_name = cb.get('display_name') or cb.get('name') or cb.get('slug', 'Unknown')
            
            # Position-based score: first result = 0.95, decreasing by 0.04
            score = max(0.95 - (i - 1) * 0.04, 0.55)
            
            # Check if any search keyword appears in name/display_name/tags
            _name = (cb.get('name', '') or '').lower()
            _dname = (cb.get('display_name', '') or '').lower()
            _tags = ' '.join(cb.get('support_tags', [])).lower()
            
            has_keyword_in_identity = any(
                kw in _name or kw in _dname or kw in _tags
                for kw in search_kws
            ) if search_kws else True
            
            if not has_keyword_in_identity:
                # Penalise: this result only matched via description/doc text
                score = max(score - 0.20, 0.40)
            
            output += f"## {i}. **{display_name}**\n\n"
            
            coll = cb.get('codecollection', {})
            collection_slug = coll.get('slug') if isinstance(coll, dict) else cb.get('collection_slug', 'N/A')
            output += f"**Plugin:** {collection_slug}\n\n"
            output += f"**Platform:** {cb.get('platform', cb.get('discovery_platform', 'N/A'))}\n\n"
            
            description = cb.get('description') or cb.get('doc') or ''
            if description:
                output += f"**Description:** {description[:500]}\n\n"
            
            # The Registry API's `tasks` field contains the Task entries
            # parsed from runbook.robot (Runbook / TaskSet type). SLI / Monitor
            # entries live in a separate `slis` field. Internal field names are
            # kept for backward compatibility; the markdown label uses the new
            # display vocabulary.
            tasks = cb.get('tasks', [])
            if tasks:
                output += "**Tasks:**\n"
                for task in tasks[:8]:
                    if isinstance(task, dict):
                        label = task.get('title') or task.get('name') or str(task)
                        desc = task.get('description') or task.get('doc')
                        output += f"- {label}" + (f": {str(desc)[:140]}\n" if desc else "\n")
                    else:
                        output += f"- {task}\n"
                output += "\n"
            
            tags = cb.get('support_tags', [])
            if tags:
                output += f"**Tags:** {', '.join(tags)}\n\n"
            
            # Relevance score is read by the chatbot's markdown parser
            output += f"**Relevance:** {int(score * 100)}%\n\n"
            
            # Source link for the markdown parser
            slug = cb.get('slug', '')
            output += f"**Source:** [{collection_slug}/skills/{slug}](/plugins/{collection_slug}/skills/{slug})\n\n"
            if cb.get('runbook_source_url'):
                output += f"**GitHub:** [{cb['runbook_source_url']}]({cb['runbook_source_url']})\n\n"
            
            output += "---\n\n"
        
        return output


class ListCodeBundlesTool(BaseTool):
    """List all Skills (formerly "CodeBundles"), optionally filtered by plugin."""
    
    def __init__(self, registry_client):
        self._client = registry_client
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="list_codebundles",
            description="List all Skills (formerly 'CodeBundles') and Plugins. Supports filtering by plugin and output formatting.",
            category="info",
            parameters=[
                ToolParameter(
                    name="format",
                    type="string",
                    description="Output format",
                    required=False,
                    default="markdown",
                    enum=["markdown", "json", "summary"]
                ),
                ToolParameter(
                    name="collection_slug",
                    type="string",
                    description="Filter by collection slug",
                    required=False
                )
            ]
        )
    
    async def execute(
        self,
        format: str = "markdown",
        collection_slug: Optional[str] = None
    ) -> str:
        """List Skills from the Registry API."""
        try:
            codebundles = await self._client.search_codebundles(
                collection_slug=collection_slug,
                max_results=200,
            )
        except Exception as e:
            logger.error(f"Registry API list failed: {e}")
            return f"Failed to list Skills: {e}"
        
        if format == "json":
            return json.dumps({"codebundles": codebundles, "count": len(codebundles)}, indent=2, default=str)
        
        if format == "summary":
            by_collection = {}
            for cb in codebundles:
                coll = cb.get('collection_slug', cb.get('codecollection', {}).get('slug', 'unknown'))
                if coll not in by_collection:
                    by_collection[coll] = []
                by_collection[coll].append(cb)
            
            output = f"# Skill Summary\n\n"
            output += f"Total: {len(codebundles)} Skills in {len(by_collection)} Plugins\n\n"
            for coll, cbs in sorted(by_collection.items()):
                output += f"## {coll} ({len(cbs)} Skills)\n\n"
            return output
        
        # Markdown format
        output = f"# Available Skills ({len(codebundles)})\n\n"
        for cb in codebundles[:50]:
            display_name = cb.get('display_name') or cb.get('name') or cb.get('slug')
            output += f"### **{display_name}**\n"
            output += f"- Plugin: {cb.get('collection_slug', cb.get('codecollection', {}).get('slug', 'N/A'))}\n"
            output += f"- Platform: {cb.get('platform', cb.get('discovery_platform', 'Unknown'))}\n"
            desc = cb.get('description') or cb.get('doc') or ''
            if desc:
                output += f"- {desc[:200]}\n"
            output += "\n"
        
        if len(codebundles) > 50:
            output += f"\n*... and {len(codebundles) - 50} more*\n"
        return output


class SearchCodeBundlesTool(BaseTool):
    """Keyword-based search for Skills (formerly "CodeBundles")."""
    
    def __init__(self, registry_client):
        self._client = registry_client
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_codebundles",
            description="Search for Skills (formerly 'CodeBundles') by keywords, tags, or platform.",
            category="search",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search query",
                    required=True
                ),
                ToolParameter(
                    name="tags",
                    type="array",
                    description="Filter by tags",
                    required=False,
                    items="string"
                ),
                ToolParameter(
                    name="platform",
                    type="string",
                    description="Filter by platform",
                    required=False
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum results",
                    required=False,
                    default=10
                )
            ]
        )
    
    async def execute(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        platform: Optional[str] = None,
        max_results: int = 10
    ) -> str:
        """Search codebundles via the Registry API."""
        search_terms = _extract_search_keywords(query)
        try:
            results = await self._client.search_codebundles(
                search=search_terms,
                platform=platform,
                tags=",".join(tags) if tags else None,
                max_results=max_results,
            )
        except Exception as e:
            logger.error(f"Registry API search failed: {e}")
            return f"Search unavailable: {e}"
        
        if not results:
            return f"No Skills found matching: {query}"
        
        output = f"# Search Results: {query}\n\n"
        output += f"Found {len(results)} result(s):\n\n"
        
        for i, cb in enumerate(results, 1):
            display_name = cb.get('display_name') or cb.get('name') or cb.get('slug')
            output += f"## {i}. **{display_name}**\n\n"
            output += f"**Plugin:** {cb.get('collection_slug', cb.get('codecollection', {}).get('slug', 'N/A'))}\n"
            output += f"**Platform:** {cb.get('platform', cb.get('discovery_platform', 'Unknown'))}\n"
            desc = cb.get('description') or cb.get('doc') or ''
            if desc:
                output += f"**Description:** {desc}\n"
            tags_list = cb.get('support_tags', [])
            if tags_list:
                output += f"**Tags:** {', '.join(tags_list)}\n"
            output += f"\n---\n\n"
        
        return output


class GetCodeBundleDetailsTool(BaseTool):
    """Get detailed information about a specific Skill (formerly "CodeBundle")."""
    
    def __init__(self, registry_client):
        self._client = registry_client
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_codebundle_details",
            description="Get detailed information about a specific Skill (formerly 'CodeBundle')",
            category="info",
            parameters=[
                ToolParameter(
                    name="slug",
                    type="string",
                    description="Skill slug",
                    required=True
                ),
                ToolParameter(
                    name="collection_slug",
                    type="string",
                    description="Plugin slug (helps disambiguate)",
                    required=False
                )
            ]
        )
    
    async def execute(
        self,
        slug: str,
        collection_slug: Optional[str] = None
    ) -> str:
        """Get Skill details from the Registry API."""
        cb = None
        
        # Try direct lookup if we have both slugs
        if collection_slug:
            try:
                cb = await self._client.get_codebundle(collection_slug, slug)
            except Exception as e:
                logger.warning(f"Direct Skill lookup failed: {e}")
        
        # Fall back to search
        if not cb:
            try:
                results = await self._client.search_codebundles(search=slug, max_results=5)
                for r in results:
                    if r.get('slug') == slug or slug in r.get('slug', ''):
                        cb = r
                        break
            except Exception as e:
                logger.error(f"Skill search failed: {e}")
                return f"Failed to fetch Skill: {e}"
        
        if not cb:
            return f"Skill not found: {slug}"
        
        display_name = cb.get('display_name') or cb.get('name') or cb.get('slug')
        output = f"# **{display_name}**\n\n"
        output += f"**Slug:** {cb.get('slug')}\n\n"
        output += f"**Plugin:** {cb.get('collection_slug', cb.get('codecollection', {}).get('slug', 'N/A'))}\n\n"
        output += f"**Platform:** {cb.get('platform', cb.get('discovery_platform', 'Unknown'))}\n\n"
        
        if cb.get('author'):
            output += f"**Author:** {cb['author']}\n\n"
        
        description = cb.get('description') or cb.get('doc') or ''
        if description:
            output += f"## Description\n\n{description}\n\n"
        
        # Internal field name `tasks` is kept for backward compatibility; the
        # markdown label uses the new display vocabulary.
        tasks = cb.get('tasks', [])
        if tasks:
            output += f"## Tasks ({len(tasks)})\n\n"
            for task in tasks:
                if isinstance(task, dict):
                    label = task.get('title') or task.get('name') or str(task)
                    name = task.get('name')
                    heading = f"{label} (`{name}`)" if label and name and label != name else label
                    desc = task.get('description') or task.get('doc')
                    read_only = task.get('readOnly')
                    chips = []
                    if read_only is False:
                        chips.append("read-write")
                    elif read_only is True:
                        chips.append("read-only")
                    if task.get('destructive'):
                        chips.append("destructive")
                    if task.get('dryRun'):
                        chips.append("dry-run")
                    output += f"- **{heading}**" + (f" — {', '.join(chips)}" if chips else "") + "\n"
                    if desc:
                        output += f"  {str(desc)[:400]}\n"
                else:
                    output += f"- {task}\n"
            output += "\n"
        
        tags = cb.get('support_tags', [])
        if tags:
            output += f"**Tags:** {', '.join(tags)}\n\n"
        
        return output
