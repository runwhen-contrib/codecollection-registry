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
    context_limit: Optional[int] = 10  # Increased from 5 for better coverage
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


class CodeBundleRequestQuery(BaseModel):
    """Request model for creating a new CodeBundle request issue"""
    platform: str
    tasks: List[str]
    original_query: Optional[str] = None
    context: Optional[str] = None
    contact_ok: bool = False


class CodeBundleRequestResponse(BaseModel):
    """Response model for CodeBundle request creation"""
    success: bool
    message: str
    issue_url: Optional[str] = None
    issue_number: Optional[int] = None


class ExistingRequestsResponse(BaseModel):
    """Response model for existing requests check"""
    found: bool
    message: str
    existing_issues: List[Dict[str, Any]] = []


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
        
        # Determine question type
        question_lower = query.question.lower()
        
        # Keywords/library questions
        is_keyword_question = any(word in question_lower for word in [
            'library', 'libraries', 'keyword', 'import', 'use ', 'how do i use',
            'rw.cli', 'rw.k8s', 'robot framework'
        ])
        
        # Documentation/how-to questions (configuration, setup, guides)
        is_docs_question = any(word in question_lower for word in [
            'how to', 'how do i', 'configure', 'configuration', 'setup', 'set up',
            'meta.yaml', 'secrets', 'credentials', 'generation rule', 'gen rule',
            'sli', 'task vs', 'what is', 'guide', 'documentation', 'example',
            'best practice', 'getting started', 'tutorial'
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
        doc_context = ""  # Documentation context
        
        if is_keyword_question:
            mcp_response = await mcp.keyword_usage_help(
                query=query.question,
                category="all"
            )
            relevant_tasks = []
            sources_used = ["MCP Keyword Search"]
        else:
            # Always search codebundles
            mcp_response = await mcp.find_codebundle(
                query=query.question,
                platform=platform,
                max_results=query.context_limit + 3  # Request more to filter
            )
            # Parse sources from the markdown response
            sources_used = _extract_sources_from_markdown(mcp_response)
            all_tasks = _parse_markdown_to_tasks(mcp_response)
            
            # Also search documentation if this looks like a docs/how-to question
            if is_docs_question:
                try:
                    doc_response = await mcp.find_documentation(
                        query=query.question,
                        category="all",
                        max_results=5
                    )
                    if doc_response and "No documentation found" not in doc_response:
                        doc_context = f"\n\n## Documentation Resources:\n{doc_response}"
                        mcp_response += doc_context
                        sources_used.append("MCP Documentation Search")
                except Exception as e:
                    logger.warning(f"Documentation search failed: {e}")
            
            # Filter results by relevance
            # With Azure embeddings (1536-dim), 70-80% is typical for good matches
            MIN_RELEVANCE = 0.55  # Include more results for better coverage
            STRONG_RELEVANCE = 0.65  # High-confidence matches
            
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
                "category": "Development & Configuration",
                "queries": [
                    "How do I set up generation rules?",
                    "How do I configure secrets in codebundles?",
                    "What goes in meta.yaml?",
                    "How do I create an SLI vs a Task?"
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
                    "Getting started with codebundle development",
                    "Show me tasks for PostgreSQL",
                    "What tasks require minimal permissions?"
                ]
            }
        ]
    }


@router.get("/check-existing-requests", response_model=ExistingRequestsResponse)
async def check_existing_requests(search_term: str):
    """
    Check if there are existing CodeBundle requests similar to what the user needs.
    
    This searches open GitHub issues in the codecollection-registry repository.
    """
    try:
        mcp = get_mcp_client()
        
        if not await mcp.is_available():
            return ExistingRequestsResponse(
                found=False,
                message="MCP service not available",
                existing_issues=[]
            )
        
        result = await mcp.call_tool("check_existing_requests", {"search_term": search_term})
        
        # Parse the response to extract issues
        if "No existing CodeBundle requests found" in result:
            return ExistingRequestsResponse(
                found=False,
                message=f"No existing requests found for '{search_term}'",
                existing_issues=[]
            )
        
        # Parse issues from the markdown response
        import re
        issues = []
        for match in re.finditer(r'\*\*#(\d+)\*\*: \[(.+?)\]\((.+?)\)', result):
            issues.append({
                "number": int(match.group(1)),
                "title": match.group(2),
                "url": match.group(3)
            })
        
        return ExistingRequestsResponse(
            found=len(issues) > 0,
            message=f"Found {len(issues)} existing request(s)",
            existing_issues=issues
        )
        
    except Exception as e:
        logger.error(f"Error checking existing requests: {e}")
        return ExistingRequestsResponse(
            found=False,
            message=f"Error checking requests: {str(e)}",
            existing_issues=[]
        )


@router.post("/request-codebundle", response_model=CodeBundleRequestResponse)
async def request_codebundle(request: CodeBundleRequestQuery):
    """
    Create a new CodeBundle request on GitHub.
    
    This creates an issue in the codecollection-registry repository using
    the codebundle-wanted template.
    """
    try:
        mcp = get_mcp_client()
        
        if not await mcp.is_available():
            raise HTTPException(
                status_code=503,
                detail="MCP service is not available"
            )
        
        result = await mcp.call_tool("request_codebundle", {
            "platform": request.platform,
            "tasks": request.tasks,
            "original_query": request.original_query,
            "context": request.context,
            "contact_ok": request.contact_ok
        })
        
        # Parse the response
        if "✅" in result and "Successfully" in result:
            # Extract issue URL and number
            import re
            url_match = re.search(r'https://github\.com/[^\s\)]+', result)
            num_match = re.search(r'#(\d+)', result)
            
            return CodeBundleRequestResponse(
                success=True,
                message="CodeBundle request created successfully!",
                issue_url=url_match.group(0) if url_match else None,
                issue_number=int(num_match.group(1)) if num_match else None
            )
        elif "⚠️" in result and "not configured" in result:
            # GitHub token not configured - return the manual instructions
            return CodeBundleRequestResponse(
                success=False,
                message=result
            )
        else:
            return CodeBundleRequestResponse(
                success=False,
                message=result
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating codebundle request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        
        system_prompt = """You are a helpful assistant that helps users find and use RunWhen CodeBundles and documentation.

CodeBundles are automation scripts for troubleshooting and managing infrastructure (Kubernetes, AWS, Azure, GCP, databases, etc.).

You have access to:
1. CodeBundles - automation scripts for specific tasks
2. Documentation - guides, tutorials, and reference materials for codebundle development
3. Libraries - Robot Framework keyword libraries (RW.CLI, RW.K8s, etc.)
4. Examples - sample codebundles and configurations

CRITICAL RULES:
1. ONLY recommend resources that DIRECTLY ADDRESS the user's specific question
2. For "how to" questions about configuration/development, prioritize documentation
3. For troubleshooting/automation questions, recommend relevant codebundles
4. Be STRICT about relevance - fewer accurate recommendations are better than many tangential ones

When recommending:
- Explain what each resource does in plain language
- For documentation, explain what the guide covers and include the URL
- For codebundles, mention the name and collection so users can find it
- Be conversational and keep responses concise but informative

If NO resources directly address the query:
- Be honest: "I couldn't find a resource specifically for [user's need]"
- Suggest the closest match IF it's genuinely useful
- For codebundle requests, suggest creating a GitHub issue
- For documentation gaps, point to https://docs.runwhen.com"""

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


