"""
MCP Chat Router

Provides chat endpoints that use the MCP server for semantic search,
combined with LLM synthesis for natural language responses.
"""
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.mcp_client import get_mcp_client, MCPClient, MCPError
from app.services.ai_service import AIEnhancementService
from app.services.ai_prompts import AIPrompts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ChatQuery(BaseModel):
    """Request model for chat queries"""
    question: str
    context_limit: Optional[int] = 5
    include_enhanced_descriptions: Optional[bool] = True


class RelevantTask(BaseModel):
    """A relevant task/codebundle from search results"""
    id: int = 0
    codebundle_name: str
    codebundle_slug: str
    collection_name: str
    collection_slug: str
    description: str
    support_tags: List[str] = []
    tasks: List[str] = []
    slis: List[str] = []
    author: str = ""
    access_level: str = "unknown"
    minimum_iam_requirements: List[str] = []
    runbook_source_url: str = ""
    relevance_score: float = 0.0
    platform: str = ""
    resource_types: List[str] = []


class ChatResponse(BaseModel):
    """Response model for chat queries"""
    answer: str
    relevant_tasks: List[RelevantTask]
    confidence_score: Optional[float] = None
    sources_used: List[str]
    query_metadata: Dict[str, Any]


class KeywordHelpQuery(BaseModel):
    """Request model for keyword help queries"""
    question: str
    category: Optional[str] = "all"


class KeywordHelpResponse(BaseModel):
    """Response model for keyword help"""
    answer: str
    query_metadata: Dict[str, Any]


# =============================================================================
# Chat Endpoints
# =============================================================================

@router.post("/query", response_model=ChatResponse)
async def query_codecollections(
    query: ChatQuery,
    db: Session = Depends(get_db)
):
    """
    Answer questions about codecollection tasks using MCP semantic search + LLM synthesis.
    
    This endpoint:
    1. Uses MCP server's semantic search to find relevant codebundles
    2. Uses Azure OpenAI to synthesize a helpful natural language response
    
    Examples:
    - "What do I run when pods are failing?"
    - "How do I debug Azure App Service issues?"
    - "Find tasks for Kubernetes troubleshooting"
    """
    try:
        mcp = get_mcp_client()
        ai_service = AIEnhancementService(db)
        
        # Check if MCP is available
        if not await mcp.is_available():
            raise HTTPException(
                status_code=503,
                detail="MCP search service is not available. Please try again later."
            )
        
        # Determine if this is a keyword/library question
        question_lower = query.question.lower()
        is_keyword_question = any(word in question_lower for word in [
            'library', 'libraries', 'keyword', 'import', 'use ', 'how do i use',
            'rw.cli', 'rw.k8s', 'robot framework'
        ])
        
        # Determine platform from question
        platform = None
        if 'kubernetes' in question_lower or 'k8s' in question_lower or 'pod' in question_lower:
            platform = "Kubernetes"
        elif 'aws' in question_lower or 'amazon' in question_lower:
            platform = "AWS"
        elif 'azure' in question_lower:
            platform = "Azure"
        elif 'gcp' in question_lower or 'google cloud' in question_lower:
            platform = "GCP"
        
        # Call MCP for semantic search
        all_tasks = []  # Initialize for later use
        if is_keyword_question:
            mcp_response = await mcp.keyword_usage_help(
                query=query.question,
                category="all"
            )
            relevant_tasks = []
            sources_used = ["MCP Keyword Search"]
        else:
            mcp_response = await mcp.find_codebundle(
                query=query.question,
                platform=platform,
                max_results=query.context_limit + 3  # Request more to filter
            )
            # Parse sources from the markdown response
            sources_used = _extract_sources_from_markdown(mcp_response)
            all_tasks = _parse_markdown_to_tasks(mcp_response)
            
            # Filter results by relevance
            # With local embeddings, 60-70% is typical for good matches
            # Don't force minimum results - if nothing is relevant, say so
            MIN_RELEVANCE = 0.60  # Good enough for semantic match
            STRONG_RELEVANCE = 0.70  # High-confidence matches
            
            relevant_tasks = []
            for t in all_tasks:
                # Include strong matches
                if t.relevance_score >= STRONG_RELEVANCE:
                    relevant_tasks.append(t)
                # Include moderate matches only if platform aligns
                elif t.relevance_score >= MIN_RELEVANCE:
                    if not platform:  # No platform specified, include it
                        relevant_tasks.append(t)
                    elif t.platform and t.platform.lower() == platform.lower():
                        relevant_tasks.append(t)
                    # Skip if platform doesn't match (e.g., AWS result for K8s query)
            
            # Limit to requested context_limit - but don't pad with irrelevant results
            relevant_tasks = relevant_tasks[:query.context_limit]
        
        # Generate LLM-synthesized answer if AI is available
        # Even if no tasks pass our strict filter, use LLM to synthesize from raw MCP context
        if ai_service.is_enabled():
            # If we have filtered relevant tasks, use those
            # If not, parse ALL tasks from MCP response for context (LLM will filter)
            tasks_for_llm = relevant_tasks if relevant_tasks else all_tasks[:query.context_limit]
            answer = await _generate_llm_answer(
                ai_service=ai_service,
                question=query.question,
                mcp_context=mcp_response,
                relevant_tasks=tasks_for_llm
            )
            # Update relevant_tasks to show user what we're referencing
            if not relevant_tasks:
                relevant_tasks = tasks_for_llm
        else:
            # Fallback to MCP response directly
            answer = mcp_response
        
        return ChatResponse(
            answer=answer,
            relevant_tasks=relevant_tasks,
            confidence_score=None,
            sources_used=sources_used,
            query_metadata={
                "query_processed_at": _get_timestamp(),
                "context_tasks_count": len(relevant_tasks),
                "search_engine": "mcp-semantic",
                "llm_enabled": ai_service.is_enabled(),
                "platform_filter": platform
            }
        )
        
    except MCPError as e:
        logger.error(f"MCP error: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing chat query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@router.post("/keywords", response_model=KeywordHelpResponse)
async def keyword_usage_help(query: KeywordHelpQuery):
    """
    Get help on using RunWhen Robot Framework keywords.
    
    Ask questions like:
    - "How do I run kubectl commands?"
    - "How do I parse JSON output?"
    - "What library handles AWS operations?"
    """
    try:
        mcp = get_mcp_client()
        
        if not await mcp.is_available():
            raise HTTPException(
                status_code=503,
                detail="MCP search service is not available."
            )
        
        answer = await mcp.keyword_usage_help(
            query=query.question,
            category=query.category or "all"
        )
        
        return KeywordHelpResponse(
            answer=answer,
            query_metadata={
                "query_processed_at": _get_timestamp(),
                "search_engine": "mcp-semantic",
                "category": query.category
            }
        )
        
    except MCPError as e:
        logger.error(f"MCP error: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing keyword query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def chat_health_check(db: Session = Depends(get_db)):
    """Check if chat service is available and configured"""
    try:
        mcp = get_mcp_client()
        mcp_health = await mcp.health_check()
        
        # Also check if AI is configured (for enhanced descriptions)
        ai_service = AIEnhancementService(db)
        
        return {
            "status": "healthy" if mcp_health.get("status") == "healthy" else "degraded",
            "mcp_status": mcp_health.get("status"),
            "mcp_semantic_search": mcp_health.get("semantic_search", {}).get("is_available", False),
            "ai_enabled": ai_service.is_enabled(),
            "ai_provider": ai_service.config.service_provider if ai_service.config else None,
            "model": ai_service.config.model_name if ai_service.config else None
        }
    except Exception as e:
        logger.error(f"Chat health check failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/examples")
async def get_example_queries():
    """Get example queries that users can ask"""
    return {
        "examples": [
            {
                "category": "Troubleshooting",
                "queries": [
                    "What do I run when pods are failing?",
                    "How do I debug Kubernetes networking issues?",
                    "Find tasks for Azure App Service problems",
                    "Troubleshoot AWS EKS cluster issues"
                ]
            },
            {
                "category": "Keywords & Libraries",
                "queries": [
                    "How do I run kubectl commands?",
                    "What library handles CLI operations?",
                    "How do I parse JSON output?",
                    "How do I use the AWS CLI in codebundles?"
                ]
            },
            {
                "category": "Platform-Specific",
                "queries": [
                    "Find Azure monitoring tasks",
                    "What Kubernetes health checks are available?",
                    "Show me GCP resource management tools",
                    "Find database troubleshooting tasks"
                ]
            },
            {
                "category": "General",
                "queries": [
                    "What codebundles are available for monitoring?",
                    "Find read-only diagnostic tasks",
                    "Show me tasks for PostgreSQL",
                    "What tasks require minimal permissions?"
                ]
            }
        ]
    }


# =============================================================================
# LLM Synthesis
# =============================================================================

async def _generate_llm_answer(
    ai_service: AIEnhancementService,
    question: str,
    mcp_context: str,
    relevant_tasks: List[RelevantTask]
) -> str:
    """
    Generate a natural language answer using the AI service.
    
    Takes the MCP search results and synthesizes a helpful response.
    """
    try:
        client = ai_service._get_ai_client()
        model_name = ai_service._get_model_name()
        
        # Build context from tasks
        task_context = _build_task_context(relevant_tasks)
        
        system_prompt = """You are a helpful assistant that helps users find and use RunWhen CodeBundles.

CodeBundles are automation scripts for troubleshooting and managing infrastructure (Kubernetes, AWS, Azure, GCP, databases, etc.).

CRITICAL RULES:
1. ONLY recommend codebundles that DIRECTLY ADDRESS the user's specific question
2. Do NOT include results just because they share a vague category (e.g., don't show generic K8s health checks for a specific networking question)
3. Be STRICT about relevance - fewer accurate recommendations are better than many tangential ones
4. If a codebundle's description doesn't clearly match the query, DON'T recommend it

When recommending:
- Explain what each recommended codebundle does in plain language
- Be conversational and match the user's tone
- Mention the codebundle name and collection so users can find it
- Keep responses concise but informative

If NO codebundles directly address the query:
- Be honest: "I couldn't find a codebundle specifically for [user's need]"
- Suggest the closest match IF it's genuinely useful, or suggest creating a GitHub issue
- Don't pad the response with irrelevant results"""

        user_prompt = f"""User Question: {question}

Available CodeBundles from search (sorted by relevance score):

{task_context}

IMPORTANT: Only recommend codebundles that DIRECTLY solve the user's problem. 
- If a codebundle doesn't specifically address their question, don't include it
- If none are truly relevant, say so honestly
- Quality over quantity - 1-2 good matches is better than 5 mediocre ones"""

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=800,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error generating LLM answer: {e}")
        # Return a simpler fallback
        return _generate_fallback_answer(question, relevant_tasks)


def _build_task_context(tasks: List[RelevantTask]) -> str:
    """Build context string from tasks for LLM"""
    if not tasks:
        return "No matching tasks found."
    
    parts = []
    for i, task in enumerate(tasks, 1):
        task_info = [
            f"## {i}. {task.codebundle_name}",
            f"Collection: {task.collection_name}",
            f"Platform: {task.platform}",
        ]
        if task.description:
            task_info.append(f"Description: {task.description}")
        if task.support_tags:
            task_info.append(f"Tags: {', '.join(task.support_tags)}")
        task_info.append(f"Relevance: {task.relevance_score:.0%}")
        parts.append("\n".join(task_info))
    
    return "\n\n".join(parts)


def _generate_fallback_answer(question: str, tasks: List[RelevantTask]) -> str:
    """Generate a simple fallback answer when LLM is not available"""
    if not tasks:
        return f"""I couldn't find any tasks matching your question: "{question}"

Would you like to request these tasks be added to the registry? You can create a GitHub issue to request new automation tasks."""

    answer_parts = [
        f"Here are the most relevant tasks for: **{question}**\n"
    ]
    
    for i, task in enumerate(tasks[:3], 1):
        answer_parts.append(f"{i}. **{task.codebundle_name}** ({task.collection_name})")
        if task.description:
            answer_parts.append(f"   {task.description[:200]}...")
        answer_parts.append("")
    
    answer_parts.append("\nSee the detailed results below for more information on each task.")
    
    return "\n".join(answer_parts)


# =============================================================================
# Helper Functions
# =============================================================================

def _get_timestamp() -> str:
    """Get current timestamp as ISO string"""
    from datetime import datetime
    return datetime.utcnow().isoformat()


def _extract_sources_from_markdown(markdown: str) -> List[str]:
    """Extract codebundle names from markdown response"""
    import re
    sources = []
    
    # Look for patterns like "## 1. Codebundle Name" or "### Codebundle Name"
    pattern = r'##\s*\d*\.?\s*(.+?)(?:\n|$)'
    matches = re.findall(pattern, markdown)
    
    for match in matches:
        name = match.strip()
        if name and not name.startswith('#'):
            sources.append(name)
    
    return sources[:10]  # Limit to 10 sources


def _parse_markdown_to_tasks(markdown: str) -> List[RelevantTask]:
    """
    Parse markdown response into structured task objects.
    
    This is a best-effort parser - the markdown format may vary.
    """
    import re
    tasks = []
    
    # Split by task headers (## 1. Name or ## Name)
    sections = re.split(r'\n##\s+\d*\.?\s*', markdown)
    
    for i, section in enumerate(sections[1:], 1):  # Skip first empty section
        lines = section.strip().split('\n')
        if not lines:
            continue
        
        # First line is the name
        name = lines[0].strip()
        
        # Parse other fields
        description = ""
        platform = ""
        collection = ""
        tags = []
        score = 0.0
        slug = ""
        git_url = ""
        
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('**Collection:**'):
                collection = line.replace('**Collection:**', '').strip().strip('`')
            elif line.startswith('**Platform:**'):
                platform = line.replace('**Platform:**', '').strip()
            elif line.startswith('**Description:**'):
                description = line.replace('**Description:**', '').strip()
            elif line.startswith('**Tags:**'):
                tags_str = line.replace('**Tags:**', '').strip()
                tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            elif line.startswith('**Relevance:**'):
                try:
                    score_str = line.replace('**Relevance:**', '').strip().rstrip('%')
                    score = float(score_str) / 100.0
                except:
                    score = 0.5
            elif line.startswith('**Source:**'):
                # Extract URL from markdown link
                match = re.search(r'\[.*?\]\((.*?)\)', line)
                if match:
                    git_url = match.group(1)
                    # Extract slug from git URL
                    if '/codebundles/' in git_url:
                        slug = git_url.split('/codebundles/')[-1].rstrip('/')
        
        if name:
            tasks.append(RelevantTask(
                id=i,
                codebundle_name=name,
                codebundle_slug=slug or name.lower().replace(' ', '-'),
                collection_name=collection,
                collection_slug=collection.lower().replace(' ', '-') if collection else "",
                description=description,
                support_tags=tags,
                platform=platform,
                relevance_score=score,
                runbook_source_url=git_url
            ))
    
    return tasks


