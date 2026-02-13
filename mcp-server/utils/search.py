"""
Search and matching utilities for RunWhen MCP Server
"""
from typing import List, Dict, Any, Set
import re


class SearchEngine:
    """Simple search engine for codebundles and libraries"""
    
    @staticmethod
    def extract_keywords(query: str) -> List[str]:
        """Extract keywords from a natural language query"""
        # Remove common words
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'which', 'what', 'where', 'how',
            'do', 'does', 'can', 'could', 'should', 'would', 'show', 'me',
            'tell', 'find', 'get', 'list', 'all', 'most', 'appropriate'
        }
        
        # Convert to lowercase and split
        words = query.lower().split()
        
        # Filter out stop words and short words
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords
    
    @staticmethod
    def calculate_relevance_score(item: Dict[str, Any], keywords: List[str], tags: List[str] = None) -> float:
        """Calculate relevance score for an item based on keywords and tags"""
        score = 0.0
        
        # Searchable text fields
        searchable_text = " ".join([
            item.get("name", ""),
            item.get("display_name", ""),
            item.get("description", ""),
            " ".join(item.get("support_tags", [])),
            " ".join(item.get("use_cases", [])),
        ]).lower()
        
        # Score based on keyword matches
        for keyword in keywords:
            # Exact match in name/title (highest priority)
            if keyword in item.get("name", "").lower():
                score += 10.0
            if keyword in item.get("display_name", "").lower():
                score += 8.0
            
            # Match in tags (high priority)
            if keyword in " ".join(item.get("support_tags", [])).lower():
                score += 5.0
            
            # Match in description (medium priority)
            if keyword in item.get("description", "").lower():
                score += 3.0
            
            # Match in use cases
            if keyword in " ".join(item.get("use_cases", [])).lower():
                score += 4.0
            
            # General match in searchable text
            if keyword in searchable_text:
                score += 1.0
        
        # Bonus for tag matches (if tags specified)
        if tags:
            item_tags = set(item.get("support_tags", []))
            for tag in tags:
                if tag.lower() in [t.lower() for t in item_tags]:
                    score += 15.0
        
        return score
    
    @staticmethod
    def search_codebundles(
        codebundles: List[Dict[str, Any]],
        query: str = None,
        tags: List[str] = None,
        collection_slug: str = None,
        platform: str = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search codebundles with various filters"""
        
        results = []
        
        # Extract keywords from query
        keywords = SearchEngine.extract_keywords(query) if query else []
        
        for cb in codebundles:
            # Filter by collection if specified
            if collection_slug and cb.get("collection_slug") != collection_slug:
                continue
            
            # Filter by platform if specified
            if platform and cb.get("platform") != platform:
                continue
            
            # Calculate relevance score
            score = SearchEngine.calculate_relevance_score(cb, keywords, tags)
            
            # Only include if score > 0 or no query/tags specified
            if score > 0 or (not query and not tags):
                results.append({
                    "codebundle": cb,
                    "score": score
                })
        
        # Sort by score (descending)
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # Return top N results
        return [r["codebundle"] for r in results[:max_results]]
    
    @staticmethod
    def search_libraries(
        libraries: List[Dict[str, Any]],
        query: str,
        category: str = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search libraries based on query"""
        
        keywords = SearchEngine.extract_keywords(query)
        results = []
        
        for lib in libraries:
            # Filter by category if specified
            if category and category != "all" and lib.get("category") != category:
                continue
            
            # Calculate relevance
            score = SearchEngine.calculate_relevance_score(lib, keywords)
            
            # Also check common use cases
            use_cases_text = " ".join(lib.get("common_use_cases", [])).lower()
            for keyword in keywords:
                if keyword in use_cases_text:
                    score += 5.0
            
            if score > 0:
                results.append({
                    "library": lib,
                    "score": score
                })
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return [r["library"] for r in results[:max_results]]
    
    @staticmethod
    def search_documentation(
        resources: List[Dict[str, Any]],
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search documentation resources"""
        
        keywords = SearchEngine.extract_keywords(query)
        results = []
        
        for resource in resources:
            score = 0.0
            
            # Check title
            title = resource.get("title", "").lower()
            for keyword in keywords:
                if keyword in title:
                    score += 10.0
            
            # Check topics
            topics = " ".join(resource.get("topics", [])).lower()
            for keyword in keywords:
                if keyword in topics:
                    score += 5.0
            
            # Check description
            description = resource.get("description", "").lower()
            for keyword in keywords:
                if keyword in description:
                    score += 3.0
            
            if score > 0:
                results.append({
                    "resource": resource,
                    "score": score
                })
        
        # Sort by score
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return [r["resource"] for r in results[:max_results]]

