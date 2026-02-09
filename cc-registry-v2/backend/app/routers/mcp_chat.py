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

class ConversationMessage(BaseModel):
    """A message in conversation history"""
    role: str  # 'user' or 'assistant'
    content: str


class ChatQuery(BaseModel):
    """Request model for chat queries"""
    question: str
    context_limit: Optional[int] = 10  # Increased from 5 for better coverage
    include_enhanced_descriptions: Optional[bool] = True
    conversation_history: Optional[List[ConversationMessage]] = None  # Previous messages for context


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
    no_match: bool = False  # True when no relevant codebundle was found
    answer_source: str = "codebundles"  # "documentation", "codebundles", "libraries", "mixed", or "system"


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
        
        # Detect follow-up questions that reference the SAME previous codebundle
        # These don't need a new semantic search, just use conversation context
        # NOTE: Phrases like "what other" or "what else" indicate wanting DIFFERENT resources,
        # so they should trigger a new search with conversation context, not a focused lookup
        is_followup_question = any(phrase in question_lower for phrase in [
            'this codebundle', 'this code bundle', 'that codebundle', 'that code bundle',
            'what else can it', 'what else does it', 'more about it',
            'same codebundle', 'same bundle', 'can it also', 'does it also',
            'what else can this', 'what else does this', 'tell me more', 'more details',
            'about this', 'about that', 'in this codebundle', 'in that codebundle',
            'show me the link', 'what is the link', 'link to this', 'link to that',
            'how do i use this', 'how do i use that', 'how to use this', 'how to use that',
            'where can i find this', 'where can i find that', 'where is this', 'where is that',
            'give me the link', 'get me the link', 'send me the link'
        ]) and query.conversation_history and len(query.conversation_history) > 0
        
        # Keywords/library questions - only trigger for questions specifically about
        # Robot Framework keywords/libraries, NOT general "use" questions like
        # "what codebundle can I use to troubleshoot X"
        is_keyword_question = any(word in question_lower for word in [
            'library', 'libraries', 'keyword', 'import ',
            'rw.cli', 'rw.k8s', 'rw.core', 'rw.aws', 'rw.azure', 'rw.gcp',
            'robot framework'
        ]) and not any(word in question_lower for word in [
            'codebundle', 'code bundle', 'troubleshoot', 'monitor', 'health check',
            'what can i use', 'what codebundle'
        ])
        
        # Documentation/how-to questions (configuration, setup, guides)
        # Note: docs are now ALWAYS searched (not gated by this flag), but this
        # classification is kept for potential future use (e.g., prioritizing doc results)
        is_docs_question = any(word in question_lower for word in [
            'how to', 'how do i', 'configure', 'configuration', 'setup', 'set up',
            'install', 'installation', 'runwhen-local', 'runwhen local',
            'secrets', 'credentials', 'generation rule', 'gen rule',
            'sli', 'task vs', 'what is', 'guide', 'documentation', 'docs', 'example',
            'best practice', 'getting started', 'tutorial', 'check the docs'
        ])
        
        # Meta questions about the system itself - should NOT show codebundles
        is_meta_question = any(phrase in question_lower for phrase in [
            'what do you have access to', 'what docs do you', 'what documentation',
            'what can you do', 'what can you help', 'what are your capabilities',
            'what tools do you have', 'what features', 'what is available',
            'how can you help', 'what kind of', 'what types of', 'list your',
            'tell me about yourself', 'what are you', 'what resources do you',
            'hello', 'hi ', 'hey ', 'help me understand', 'introduce yourself'
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
        relevant_tasks = []  # Initialize
        mcp_tools_called = []  # Track which MCP tools were called
        answer_source = "codebundles"  # Default, overridden per branch
        explicitly_wants_codebundles = False  # Set True when user asks "what codebundles..."
        
        # Handle follow-up questions - do a focused search on the codebundle from conversation
        if is_followup_question:
            sources_used = ["Conversation Context"]
            
            # Extract codebundle name from conversation history
            codebundle_name = None
            for msg in reversed(query.conversation_history):
                if msg.role == 'assistant':
                    # Look for codebundle mentions like "azure-appservice-webapp-ops"
                    import re
                    match = re.search(r'\b([a-z]+-[a-z0-9-]+-[a-z0-9-]+)\b', msg.content.lower())
                    if match:
                        codebundle_name = match.group(1)
                        break
            
            # If we found a codebundle name, search specifically for it
            focused_tasks = []
            if codebundle_name:
                try:
                    mcp_response = await mcp.find_codebundle(
                        query=codebundle_name,  # Search for the specific codebundle
                        platform=None,
                        max_results=3
                    )
                    mcp_tools_called.append("find_codebundle")
                    focused_tasks = _parse_markdown_to_tasks(mcp_response)
                    # Filter to just the one we're discussing
                    focused_tasks = [t for t in focused_tasks if codebundle_name in (t.codebundle_slug or '').lower()][:1]
                    sources_used.append("MCP Codebundle Lookup")
                except Exception as e:
                    logger.warning(f"Focused codebundle search failed: {e}")
                    mcp_response = ""
            else:
                mcp_response = ""
            
            # Go to LLM with conversation history + focused context
            if ai_service.is_enabled():
                # For follow-ups, pass conversation history which contains the codebundle info
                # Even if the focused search fails, the LLM can answer from conversation
                answer = await _generate_llm_answer(
                    ai_service=ai_service,
                    question=query.question,
                    mcp_context=mcp_response if mcp_response else "Answer from conversation context only",
                    relevant_tasks=focused_tasks,
                    conversation_history=query.conversation_history,
                    is_followup=True  # Flag to adjust LLM behavior
                )
            else:
                answer = "I can answer follow-up questions better when AI is enabled. Please rephrase your question with more context."
            
            response = ChatResponse(
                answer=answer,
                relevant_tasks=[],  # Don't show codebundle cards for follow-ups
                confidence_score=None,
                sources_used=sources_used,
                query_metadata={
                    "query_processed_at": _get_timestamp(),
                    "context_tasks_count": len(focused_tasks),
                    "is_followup": True,
                    "focused_codebundle": codebundle_name,
                    "mcp_tools": mcp_tools_called
                }
            )
            
            # Store chat for debugging
            try:
                from app.routers.chat_debug import store_chat_debug, ChatDebugEntry
                debug_entry = ChatDebugEntry(
                    timestamp=_get_timestamp(),
                    question=query.question,
                    conversation_history=[{"role": msg.role, "content": msg.content} for msg in (query.conversation_history or [])],
                    mcp_response=mcp_response[:1000] if mcp_response else "No new search - used conversation context",
                    relevant_tasks_count=len(focused_tasks),
                    relevant_tasks=[{
                        "name": t.codebundle_name,
                        "slug": t.codebundle_slug,
                        "relevance_score": t.relevance_score,
                        "platform": t.platform,
                        "description": t.description[:200] if t.description else ""
                    } for t in focused_tasks],
                    llm_system_prompt="",
                    llm_user_prompt="",
                    llm_response=answer[:1000],
                    final_answer=answer,
                    no_match_flag=False,  # Follow-ups shouldn't trigger no_match
                    query_metadata={
                        "platform_detected": None,
                        "all_tasks_count": len(focused_tasks),
                        "filtered_tasks_count": len(focused_tasks),
                        "conversation_length": len(query.conversation_history),
                        "ai_enabled": ai_service.is_enabled(),
                        "is_followup": True,
                        "focused_codebundle": codebundle_name
                    }
                )
                store_chat_debug(debug_entry)
            except Exception as e:
                logger.warning(f"Failed to store followup chat debug: {e}")
            
            return response
        
        if is_meta_question:
            # Meta questions about the system - don't search codebundles
            mcp_response = """# RunWhen Assistant Capabilities

I have access to:

1. **CodeBundles** - Automation scripts for troubleshooting and managing infrastructure:
   - Kubernetes (pods, deployments, services, ingress, etc.)
   - AWS (EC2, EKS, RDS, Lambda, S3, etc.)
   - Azure (AKS, App Service, VMs, databases, etc.)
   - GCP (GKE, Cloud Run, Cloud SQL, etc.)
   - Databases (PostgreSQL, Redis, MongoDB, etc.)

2. **Documentation** - I can answer questions using RunWhen docs:
   - RunWhen Local installation and configuration
   - CodeBundle development guides
   - Cloud discovery setup (Kubernetes, AWS, Azure, GCP)
   - Robot Framework syntax and library references (RW.CLI, RW.Core, RW.K8s)
   - Best practices, troubleshooting, and FAQs

3. **Libraries** - Robot Framework keyword libraries for automation

**Ask me things like:**
- "How do I install runwhen-local?"
- "What codebundles do you have for Kubernetes?"
- "How do I troubleshoot Azure App Service?"
- "How do I configure cloud discovery?"
- "How do I create a new CodeBundle?"
"""
            relevant_tasks = []
            sources_used = ["System Information"]
            answer_source = "system"
        elif is_keyword_question:
            mcp_response = await mcp.keyword_usage_help(
                query=query.question,
                category="all"
            )
            mcp_tools_called.append("keyword_usage_help")
            relevant_tasks = []
            sources_used = ["MCP Keyword Search"]
            answer_source = "libraries"
        else:
            # Enhance search query with conversation context for better results
            search_query = query.question
            
            # Detect if user is explicitly asking for codebundles
            # e.g. "what codebundles are useful for this", "show me codebundles", "which codebundles"
            explicitly_wants_codebundles = any(phrase in question_lower for phrase in [
                'what codebundle', 'which codebundle', 'show me codebundle',
                'find codebundle', 'find me codebundle', 'list codebundle',
                'what code bundle', 'which code bundle', 'show me code bundle',
                'codebundles for', 'codebundle for', 'codebundles can',
                'recommend codebundle', 'suggest codebundle',
                'useful codebundle', 'relevant codebundle',
            ])
            if explicitly_wants_codebundles:
                answer_source = "codebundles"  # Force codebundles, don't let LLM override to docs
            
            # If this is a follow-up that references conversation context
            # (e.g., "what codebundles for this", "different codebundle", "more options"),
            # augment the search with the original user question so the search has real terms
            if query.conversation_history and len(query.conversation_history) > 0:
                # Check if current question needs context enrichment
                needs_context = False
                
                # Vague follow-ups that reference "this", "that", or ask for alternatives
                vague_indicators = [
                    'different', 'another', 'other', 'alternative', 'else',
                    'something else', 'more options', 'other options'
                ]
                # Context-dependent references - query mentions "this" or "for that" without specifics
                context_references = [
                    'for this', 'for that', 'about this', 'about that',
                    'useful for this', 'related to this', 'help with this',
                ]
                
                is_vague = any(indicator in question_lower for indicator in vague_indicators) and len(query.question.split()) < 15
                references_context = any(ref in question_lower for ref in context_references)
                
                needs_context = is_vague or references_context or explicitly_wants_codebundles
                
                if needs_context:
                    # Find the original user question for context
                    original_question = None
                    for msg in query.conversation_history:
                        if msg.role == 'user':
                            original_question = msg.content
                            break
                    
                    if original_question:
                        # Combine context: "what codebundles are useful" + "pods stuck CrashLoopBackOff"
                        search_query = f"{original_question} {query.question}"
                        logger.info(f"Enhanced query with conversation context: '{query.question}' -> '{search_query}'")
            
            # Always search codebundles
            mcp_response = await mcp.find_codebundle(
                query=search_query,
                platform=platform,
                max_results=query.context_limit + 3  # Request more to filter
            )
            mcp_tools_called.append("find_codebundle")
            # Parse sources from the markdown response
            sources_used = _extract_sources_from_markdown(mcp_response)
            all_tasks = _parse_markdown_to_tasks(mcp_response)
            
            # Always search documentation alongside codebundles
            # Documentation can answer how-to, setup, configuration, and conceptual questions
            # that codebundles alone cannot address
            try:
                doc_response = await mcp.find_documentation(
                    query=query.question,
                    category="all",
                    max_results=5
                )
                mcp_tools_called.append("find_documentation")
                if doc_response and "No documentation found" not in doc_response:
                    doc_context = f"\n\n## Documentation Resources:\n{doc_response}"
                    mcp_response += doc_context
                    sources_used.append("MCP Documentation Search")
                    logger.info(f"Documentation search returned results for: {query.question[:80]}")
                else:
                    logger.info(f"No documentation found for: {query.question[:80]}")
            except Exception as e:
                logger.warning(f"Documentation search failed: {e}")
            
            # Filter results by relevance and specificity
            # With Azure embeddings (1536-dim), 70-80% is typical for good matches
            MIN_RELEVANCE = 0.58  # Minimum to show
            STRONG_RELEVANCE = 0.64  # High-confidence matches get priority
            
            # Detect specific resource types in query to filter irrelevant results
            query_lower = question_lower
            resource_hints = []
            resource_excludes = []  # Explicitly exclude these
            if 'app service' in query_lower or 'webapp' in query_lower or 'web app' in query_lower:
                resource_hints = ['appservice-webapp', 'appservice-plan', 'webapp']
                resource_excludes = ['functionapp', 'function-', 'vmss', 'aks', 'appgateway', '-db-']
            elif 'aks' in query_lower:
                resource_hints = ['aks']
                resource_excludes = ['appservice', 'vmss']
            elif 'vmss' in query_lower or 'vm scale' in query_lower:
                resource_hints = ['vmss']
            elif 'function' in query_lower or 'functionapp' in query_lower:
                resource_hints = ['function', 'functionapp']
                resource_excludes = ['webapp-health', 'webapp-ops']
            elif 'container' in query_lower:
                resource_hints = ['container']
            
            relevant_tasks = []
            for t in all_tasks:
                # Skip if below minimum
                if t.relevance_score < MIN_RELEVANCE:
                    continue
                
                # If we detected specific resource hints, filter by them
                if resource_hints or resource_excludes:
                    slug_lower = (t.codebundle_slug or '').lower()
                    name_lower = (t.codebundle_name or '').lower()
                    combined = slug_lower + ' ' + name_lower
                    
                    # Explicitly exclude certain resource types
                    if resource_excludes:
                        if any(excl in combined for excl in resource_excludes):
                            continue
                    
                    # Check if this codebundle matches the resource hint
                    if resource_hints:
                        matches_hint = any(hint in combined for hint in resource_hints)
                        # Only include if it matches, OR if it's a very strong match (>70%)
                        if not matches_hint and t.relevance_score < 0.70:
                            continue
                
                # Include if platform matches (or no platform specified)
                if platform:
                    if not t.platform or t.platform.lower() != platform.lower():
                        # Platform mismatch - only include very strong matches
                        if t.relevance_score < 0.70:
                            continue
                
                relevant_tasks.append(t)
            
            # Sort by relevance (highest first) and limit
            relevant_tasks.sort(key=lambda x: x.relevance_score, reverse=True)
            relevant_tasks = relevant_tasks[:min(query.context_limit, 5)]  # Cap at 5 for cleaner UI
        
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
                relevant_tasks=tasks_for_llm,
                conversation_history=query.conversation_history,
                doc_context=doc_context
            )
            # Update relevant_tasks to show user what we're referencing
            if not relevant_tasks:
                relevant_tasks = tasks_for_llm
        else:
            # Fallback to MCP response directly
            answer = mcp_response
        
        # Check if LLM indicated no matching codebundle
        no_match = "[NO_MATCHING_CODEBUNDLE]" in answer
        if no_match:
            # Remove the marker from the displayed answer
            answer = answer.replace("[NO_MATCHING_CODEBUNDLE]", "").strip()
        
        # Detect answer source from LLM's [SOURCE:...] tag
        # Only override if answer_source is still the default (not set by meta/keyword/explicit branches)
        import re
        source_match = re.match(r'\[SOURCE:(documentation|codebundles|libraries|mixed)\]', answer)
        if source_match:
            # Always strip the tag from the displayed answer
            llm_source = source_match.group(1)
            answer = answer[source_match.end():].strip()
            
            # Only let the LLM override source if the user didn't explicitly ask for something
            if answer_source == "codebundles" and not explicitly_wants_codebundles:
                answer_source = llm_source
        
        # Fallback heuristics (only when source is still the default)
        if answer_source == "codebundles" and not explicitly_wants_codebundles:
            if doc_context and not relevant_tasks:
                answer_source = "documentation"
            elif doc_context and relevant_tasks:
                answer_source = "mixed"
        
        # When answer is from documentation, don't attach codebundle cards
        response_tasks = relevant_tasks if answer_source != "documentation" else []
        
        response = ChatResponse(
            answer=answer,
            relevant_tasks=response_tasks,
            confidence_score=None,
            sources_used=sources_used,
            query_metadata={
                "query_processed_at": _get_timestamp(),
                "context_tasks_count": len(relevant_tasks),
                "search_engine": "mcp-semantic",
                "llm_enabled": ai_service.is_enabled(),
                "platform_filter": platform,
                "mcp_tools": mcp_tools_called
            },
            no_match=no_match,
            answer_source=answer_source
        )
        
        # Store chat for debugging (non-blocking, best effort)
        try:
            from app.routers.chat_debug import store_chat_debug, ChatDebugEntry
            debug_entry = ChatDebugEntry(
                timestamp=_get_timestamp(),
                question=query.question,
                conversation_history=[{"role": msg.role, "content": msg.content} for msg in (query.conversation_history or [])],
                mcp_response=mcp_response[:5000] if len(mcp_response) > 5000 else mcp_response,  # Truncate long responses
                relevant_tasks_count=len(relevant_tasks),
                relevant_tasks=[{
                    "name": t.codebundle_name,
                    "slug": t.codebundle_slug,
                    "relevance_score": t.relevance_score,
                    "platform": t.platform,
                    "description": t.description[:200] if t.description else ""
                } for t in relevant_tasks[:10]],  # Limit to top 10
                llm_system_prompt="",  # Don't store full prompts for regular queries
                llm_user_prompt="",
                llm_response=answer[:2000] if len(answer) > 2000 else answer,  # Truncate
                final_answer=answer,
                no_match_flag=no_match,
                query_metadata={
                    "platform_detected": platform,
                    "all_tasks_count": len(all_tasks),
                    "filtered_tasks_count": len(relevant_tasks),
                    "conversation_length": len(query.conversation_history) if query.conversation_history else 0,
                    "ai_enabled": ai_service.is_enabled()
                }
            )
            store_chat_debug(debug_entry)
        except Exception as e:
            logger.warning(f"Failed to store chat debug entry: {e}")
        
        return response
        
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
    """Get example queries that users can ask - designed to showcase tool capabilities"""
    return {
        "examples": [
            {
                "category": "Kubernetes Operations",
                "icon": "kubernetes",
                "queries": [
                    "My pods are stuck in CrashLoopBackOff, what should I check?",
                    "Help me troubleshoot a deployment that won't roll out",
                    "My nodes are under resource pressure, what can I do?",
                    "I'm having persistent volume claim issues, how do I diagnose this?"
                ]
            },
            {
                "category": "Azure Cloud",
                "icon": "azure",
                "queries": [
                    "How do I scale out my Azure App Service when traffic spikes?",
                    "Can you help me check if my Azure SQL database is healthy?",
                    "My Application Gateway backend pool is showing unhealthy, what's wrong?",
                    "I need to diagnose issues with my AKS cluster"
                ]
            },
            {
                "category": "AWS Cloud",
                "icon": "aws",
                "queries": [
                    "How can I monitor the health of my EKS cluster?",
                    "I need help analyzing CloudWatch metrics for anomalies",
                    "My EC2 instances are having performance issues, where do I start?",
                    "Help me debug Lambda functions that are timing out"
                ]
            },
            {
                "category": "Development Help",
                "icon": "code",
                "queries": [
                    "I'm new to writing codebundles, how do I run kubectl commands?",
                    "What's the difference between SLI and TaskSet codebundles?",
                    "How do I configure secrets and credentials for my workspace?",
                    "Can you show me how to parse JSON output in Robot Framework?"
                ]
            },
            {
                "category": "Database & Monitoring",
                "icon": "database",
                "queries": [
                    "My Postgres connections are timing out, how do I troubleshoot this?",
                    "Is there a way to check if Prometheus and Grafana are healthy?",
                    "I need to verify database replication is working correctly",
                    "Help me troubleshoot Redis cache connection issues"
                ]
            },
            {
                "category": "Getting Started",
                "icon": "rocket",
                "queries": [
                    "I'm new here, what are the most useful codebundles for SRE work?",
                    "Show me some basic health check examples I can learn from",
                    "What tasks can I run with minimal cloud permissions?",
                    "Can you give me an overview of all the codecollections?"
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
    relevant_tasks: List[RelevantTask],
    conversation_history: Optional[List[ConversationMessage]] = None,
    is_followup: bool = False,
    doc_context: str = ""
) -> str:
    """
    Generate a natural language answer using the AI service.
    
    Takes the MCP search results and synthesizes a helpful response.
    Includes conversation history for context-aware follow-up questions.
    
    Args:
        is_followup: If True, prioritizes conversation context over search results
        doc_context: Documentation search results to include alongside codebundle context
    """
    try:
        client = ai_service._get_ai_client()
        model_name = ai_service._get_model_name()
        
        # Build context from tasks
        task_context = _build_task_context(relevant_tasks)
        
        system_prompt = """You are a helpful assistant that helps users find and use RunWhen CodeBundles, documentation, and guides.

CodeBundles are automation scripts for troubleshooting and managing infrastructure (Kubernetes, AWS, Azure, GCP, databases, etc.).

You have access to TWO key sources of knowledge:
1. **CodeBundles** - automation scripts for specific operational tasks (troubleshooting, monitoring, scaling, etc.)
2. **Documentation** - guides, tutorials, installation instructions, configuration references, FAQs, and conceptual explanations about RunWhen products, runwhen-local, generation rules, secrets, SLIs, tasks, etc.

Additionally:
3. Libraries - Robot Framework keyword libraries (RW.CLI, RW.K8s, etc.)
4. Examples - sample codebundles and configurations

CRITICAL: ANSWERING FROM DOCUMENTATION
- When documentation results are provided, READ THEM CAREFULLY and use their CONTENT to answer the question directly
- Do NOT just provide a link and say "check the docs" - actually summarize/explain the relevant information FROM the docs
- For installation, setup, configuration, and conceptual questions, documentation is your PRIMARY source
- Include documentation links as references AFTER providing the actual answer content
- If the docs contain step-by-step instructions, reproduce or summarize the key steps in your answer

FORMATTING RULES:
- Always use **bold** for CodeBundle names (e.g., **azure-appservice-webapp-ops**)
- Use bullet points for listing tasks or capabilities
- Keep responses focused and scannable

CRITICAL RULES:
1. ONLY recommend resources that DIRECTLY ADDRESS the user's specific question
2. For "how to" questions about installation, configuration, setup, or development: PRIORITIZE DOCUMENTATION and answer from its content
3. For troubleshooting/automation questions: recommend relevant codebundles
4. For mixed questions: provide BOTH documentation answers AND relevant codebundles
5. Be STRICT about relevance - fewer accurate recommendations are better than many tangential ones
6. IGNORE results that don't match the user's platform (e.g., don't show Kubernetes results for Azure App Service questions)
7. REMEMBER the conversation history - if the user refers to "this codebundle" or "it", they mean the one discussed previously
8. If the user asks about YOU or what YOU can do, answer about your capabilities, DON'T search for codebundles
9. When you see kubectl output or command output, IMMEDIATELY ask clarifying questions before recommending specific codebundles
10. For Kubernetes troubleshooting, always consider BOTH the workload level (Deployment/StatefulSet) AND pod level - don't assume one without asking

ASK CLARIFYING QUESTIONS PROACTIVELY when context is missing:
- If kubectl output shows pods in error state (CrashLoopBackOff, Error, etc.), ask: "Are these standalone Pods or part of a Deployment, StatefulSet, or DaemonSet?"
- If the user asks about Azure App Service, ask: "Are you working with a Web App, Function App, or Container App?"
- If the user asks about scaling, ask: "Do you want to scale up (more resources) or scale out (more instances)?"
- If the user asks about databases, ask which database system (Postgres, MySQL, Redis, etc.)
- If the user mentions a generic resource (pods, containers, services), ask for the workload type (Deployment, StatefulSet, etc.)
- Keep clarifying questions short and provide 2-3 options
- ASK IMMEDIATELY in your first response if critical context is missing - don't wait for follow-ups

When recommending:
- Always use **bold** for CodeBundle names
- Explain what each resource does in plain language
- For documentation: EXPLAIN what the docs say (don't just link) and include the URL as a reference
- For codebundles: mention the SPECIFIC TASKS it contains that are relevant
- Be conversational and keep responses concise but informative
- If multiple layers of troubleshooting exist (e.g., Pod-level AND Deployment-level), mention both options
- For Kubernetes issues, consider both workload-level (Deployment, StatefulSet) and resource-level (Pod, Container) codebundles

If NO resources directly address the query:
- Start your response with exactly: "[NO_MATCHING_CODEBUNDLE]"
- Be honest: "I couldn't find a codebundle specifically for [user's need]"
- Don't show marginally related results just to have something
- Tell them they can request this automation by clicking the "Request CodeBundle" button below
- Keep the response short since the button will handle the request"""

        # Build messages array with conversation history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if available
        if conversation_history:
            for msg in conversation_history[-6:]:  # Keep last 6 messages for context (3 turns)
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Add current question with context
        if is_followup:
            # For follow-ups, emphasize using conversation context
            user_prompt = f"""User Question: {question}

IMPORTANT - THIS IS A FOLLOW-UP QUESTION:
The user is asking about CodeBundles we JUST discussed in the conversation above.

- Look at the conversation history to find the CodeBundle names, links, and details
- If they're asking for a link, the CodeBundle slug/name is in the format: `/collections/COLLECTION-SLUG/codebundles/CODEBUNDLE-SLUG`
- If they're asking "how to use" or "more info", refer to the CodeBundle we already mentioned
- DO NOT say "I couldn't find" - we literally just discussed it!
- Answer directly from the conversation context

{f"New search results (if available):{chr(10)}{task_context}" if task_context else "No new search performed - use conversation context only."}"""
        else:
            # Build documentation section for the prompt
            doc_section = ""
            if doc_context:
                doc_section = f"""

## Documentation Results:
{doc_context}

"""
            
            user_prompt = f"""User Question: {question}

## Available CodeBundles from search (sorted by relevance score):

{task_context}
{doc_section}
ANSWER SOURCE CLASSIFICATION - You MUST start your response with exactly one of these tags:
- [SOURCE:documentation] — if your answer is primarily based on documentation results (installation, setup, how-to, configuration, conceptual questions)
- [SOURCE:codebundles] — if your answer recommends specific CodeBundles for automation/troubleshooting
- [SOURCE:libraries] — if your answer is about Robot Framework keyword libraries (RW.CLI, RW.K8s, etc.)
- [SOURCE:mixed] — if your answer uses BOTH documentation content AND CodeBundle recommendations

CRITICAL RULES FOR DOCUMENTATION-SOURCED ANSWERS:
- If documentation results answer the user's question, USE THEM as your primary source
- For documentation answers: provide the actual content/steps from the docs, DO NOT recommend or mention CodeBundles at all
- For documentation answers: include documentation URLs as references at the end
- Do NOT mix in CodeBundle suggestions when the answer clearly comes from documentation
- The user will see CodeBundle cards separately — you do NOT need to mention them in your text

CRITICAL RULES FOR CODEBUNDLE-SOURCED ANSWERS:
- Only recommend codebundles that DIRECTLY solve the user's problem
- If a codebundle doesn't specifically address their question, don't include it
- Quality over quantity - 1-2 good matches is better than 5 mediocre ones

GENERAL RULES:
- If the user is asking a follow-up about a previously mentioned codebundle, answer based on the conversation history
- If documentation fully answers the question, use [SOURCE:documentation] — do NOT force CodeBundle recommendations"""

        messages.append({"role": "user", "content": user_prompt})

        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
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
        # Include actual tasks/capabilities - this is what users search for
        if task.tasks:
            task_info.append(f"Available Tasks: {', '.join(task.tasks[:8])}")
        if task.slis:
            task_info.append(f"Available SLIs: {', '.join(task.slis[:5])}")
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
        
        task_list = []  # Individual tasks within the codebundle
        sli_list = []
        in_tasks_section = False
        in_capabilities_section = False
        
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('**Collection:**'):
                collection = line.replace('**Collection:**', '').strip().strip('`')
                in_tasks_section = False
                in_capabilities_section = False
            elif line.startswith('**Platform:**'):
                platform = line.replace('**Platform:**', '').strip()
                in_tasks_section = False
                in_capabilities_section = False
            elif line.startswith('**Description:**'):
                description = line.replace('**Description:**', '').strip()
                in_tasks_section = False
                in_capabilities_section = False
            elif line.startswith('**Available Tasks:**'):
                in_tasks_section = True
                in_capabilities_section = False
            elif line.startswith('**Capabilities:**'):
                in_tasks_section = False
                in_capabilities_section = True
            elif line.startswith('**Tags:**'):
                tags_str = line.replace('**Tags:**', '').strip()
                tags = [t.strip() for t in tags_str.split(',') if t.strip()]
                in_tasks_section = False
                in_capabilities_section = False
            elif line.startswith('**Relevance:**'):
                try:
                    score_str = line.replace('**Relevance:**', '').strip().rstrip('%')
                    score = float(score_str) / 100.0
                except:
                    score = 0.5
                in_tasks_section = False
                in_capabilities_section = False
            elif line.startswith('**Source:**'):
                # Extract URL from markdown link
                match = re.search(r'\[.*?\]\((.*?)\)', line)
                if match:
                    git_url = match.group(1)
                    # Extract slug from git URL
                    if '/codebundles/' in git_url:
                        slug = git_url.split('/codebundles/')[-1].rstrip('/')
                in_tasks_section = False
                in_capabilities_section = False
            elif line.startswith('- ') and (in_tasks_section or in_capabilities_section):
                # This is a task item
                task_item = line[2:].strip()
                if task_item:
                    task_list.append(task_item)
        
        if name:
            tasks.append(RelevantTask(
                id=i,
                codebundle_name=name,
                codebundle_slug=slug or name.lower().replace(' ', '-'),
                collection_name=collection,
                collection_slug=collection.lower().replace(' ', '-') if collection else "",
                description=description,
                support_tags=tags,
                tasks=task_list,  # Individual tasks from the codebundle
                slis=sli_list,
                platform=platform,
                relevance_score=score,
                runbook_source_url=git_url
            ))
    
    return tasks


