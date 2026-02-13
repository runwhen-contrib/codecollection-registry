"""
Chat Debug Router - Tools for diagnosing chat quality issues
"""
import logging
import json
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.services.mcp_client import get_mcp_client
from app.services.ai_service import AIEnhancementService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat/debug", tags=["chat-debug"])


class ChatDebugEntry(BaseModel):
    """A logged chat interaction for debugging"""
    timestamp: str
    question: str
    conversation_history: List[Dict[str, str]] = []
    mcp_response: str
    relevant_tasks_count: int
    relevant_tasks: List[Dict[str, Any]]
    llm_system_prompt: str
    llm_user_prompt: str
    llm_response: str
    final_answer: str
    no_match_flag: bool
    query_metadata: Dict[str, Any]


class ChatDebugRequest(BaseModel):
    """Request to test a chat interaction with full debugging"""
    question: str
    conversation_history: Optional[List[Dict[str, str]]] = None
    context_limit: Optional[int] = 10


class ChatDebugResponse(BaseModel):
    """Response with full debugging information"""
    debug_entry: ChatDebugEntry
    analysis: Dict[str, Any]
    recommendations: List[str]


# In-memory storage for recent chat interactions (last 100)
# In production, this should be a database table or Redis
recent_chats: List[ChatDebugEntry] = []
MAX_STORED_CHATS = 100


def store_chat_debug(entry: ChatDebugEntry):
    """Store a chat debug entry"""
    global recent_chats
    recent_chats.append(entry)
    # Keep only last MAX_STORED_CHATS entries
    if len(recent_chats) > MAX_STORED_CHATS:
        recent_chats = recent_chats[-MAX_STORED_CHATS:]


@router.get("/recent-chats")
async def get_recent_chats(
    limit: int = Query(default=20, le=100),
    include_prompts: bool = Query(default=False, description="Include full prompts in response")
):
    """
    Get recent chat interactions for debugging.
    
    This shows the last N chat interactions with their full context.
    Use this to identify patterns in poor quality responses.
    """
    chats = recent_chats[-limit:]
    
    if not include_prompts:
        # Strip out lengthy prompts for summary view
        simplified_chats = []
        for chat in chats:
            simplified = chat.dict()
            simplified['llm_system_prompt'] = f"[{len(chat.llm_system_prompt)} chars]"
            simplified['llm_user_prompt'] = f"[{len(chat.llm_user_prompt)} chars]"
            simplified['mcp_response'] = f"[{len(chat.mcp_response)} chars]"
            simplified_chats.append(simplified)
        return {
            "count": len(simplified_chats),
            "chats": simplified_chats
        }
    
    return {
        "count": len(chats),
        "chats": [chat.dict() for chat in chats]
    }


@router.get("/analyze-quality")
async def analyze_chat_quality(
    window_hours: int = Query(default=24, description="Analyze chats from last N hours")
):
    """
    Analyze overall chat quality metrics.
    
    Returns statistics about:
    - No-match rate (how often we fail to find relevant codebundles)
    - Average number of relevant tasks found
    - Common patterns in failed queries
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=window_hours)
    
    relevant_chats = [
        chat for chat in recent_chats
        if datetime.fromisoformat(chat.timestamp) > cutoff_time
    ]
    
    if not relevant_chats:
        return {
            "message": f"No chats found in the last {window_hours} hours",
            "stats": {}
        }
    
    # Calculate stats
    total_chats = len(relevant_chats)
    no_match_count = sum(1 for chat in relevant_chats if chat.no_match_flag)
    zero_tasks_count = sum(1 for chat in relevant_chats if chat.relevant_tasks_count == 0)
    
    avg_tasks = sum(chat.relevant_tasks_count for chat in relevant_chats) / total_chats if total_chats > 0 else 0
    
    # Identify queries that resulted in no matches
    no_match_queries = [
        {
            "question": chat.question,
            "timestamp": chat.timestamp,
            "conversation_length": len(chat.conversation_history)
        }
        for chat in relevant_chats if chat.no_match_flag
    ]
    
    # Identify follow-up questions (have conversation history)
    followup_chats = [chat for chat in relevant_chats if len(chat.conversation_history) > 0]
    followup_no_match = [chat for chat in followup_chats if chat.no_match_flag]
    
    return {
        "time_window_hours": window_hours,
        "total_chats": total_chats,
        "stats": {
            "no_match_rate": f"{(no_match_count / total_chats * 100):.1f}%",
            "no_match_count": no_match_count,
            "zero_tasks_rate": f"{(zero_tasks_count / total_chats * 100):.1f}%",
            "zero_tasks_count": zero_tasks_count,
            "average_tasks_found": f"{avg_tasks:.1f}",
            "follow_up_questions": len(followup_chats),
            "follow_up_no_match_rate": f"{(len(followup_no_match) / len(followup_chats) * 100):.1f}%" if followup_chats else "N/A"
        },
        "problem_queries": no_match_queries[:10],  # Show top 10 failed queries
        "recommendations": _generate_quality_recommendations({
            "no_match_rate": no_match_count / total_chats if total_chats > 0 else 0,
            "followup_no_match_rate": len(followup_no_match) / len(followup_chats) if followup_chats else 0,
            "avg_tasks": avg_tasks
        })
    }


@router.post("/test-query", response_model=ChatDebugResponse)
async def test_chat_query(
    request: ChatDebugRequest,
    db: Session = Depends(get_db)
):
    """
    Test a chat query with full debugging information.
    
    This endpoint runs a chat query and returns detailed debugging info:
    - Raw MCP search results
    - Filtered relevant tasks
    - Full LLM prompts sent
    - Raw LLM response received
    - Final processed answer
    - Analysis and recommendations
    
    Use this to diagnose why a specific query produces poor results.
    """
    try:
        mcp = get_mcp_client()
        ai_service = AIEnhancementService(db)
        
        if not await mcp.is_available():
            raise HTTPException(
                status_code=503,
                detail="MCP search service is not available"
            )
        
        question = request.question
        conversation_history = request.conversation_history or []
        
        logger.info(f"[DEBUG] Testing query: {question}")
        logger.info(f"[DEBUG] Conversation history length: {len(conversation_history)}")
        
        # Step 1: Perform MCP search
        question_lower = question.lower()
        
        # Determine platform
        platform = None
        if 'kubernetes' in question_lower or 'k8s' in question_lower or 'pod' in question_lower or 'deployment' in question_lower:
            platform = "Kubernetes"
        elif 'aws' in question_lower or 'amazon' in question_lower:
            platform = "AWS"
        elif 'azure' in question_lower:
            platform = "Azure"
        elif 'gcp' in question_lower or 'google cloud' in question_lower:
            platform = "GCP"
        
        logger.info(f"[DEBUG] Detected platform: {platform}")
        
        # Perform MCP search
        mcp_response = await mcp.find_codebundle(
            query=question,
            platform=platform,
            max_results=request.context_limit + 3
        )
        
        logger.info(f"[DEBUG] MCP response length: {len(mcp_response)} chars")
        
        # Step 2: Parse tasks from MCP response
        from app.routers.mcp_chat import _parse_markdown_to_tasks
        all_tasks = _parse_markdown_to_tasks(mcp_response)
        
        logger.info(f"[DEBUG] Parsed {len(all_tasks)} tasks from MCP response")
        for i, task in enumerate(all_tasks[:5], 1):
            logger.info(f"[DEBUG]   Task {i}: {task.codebundle_name} (score: {task.relevance_score:.0%})")
        
        # Step 3: Filter relevant tasks
        MIN_RELEVANCE = 0.58
        relevant_tasks = [t for t in all_tasks if t.relevance_score >= MIN_RELEVANCE]
        relevant_tasks.sort(key=lambda x: x.relevance_score, reverse=True)
        relevant_tasks = relevant_tasks[:min(request.context_limit, 5)]
        
        logger.info(f"[DEBUG] Filtered to {len(relevant_tasks)} relevant tasks (min score: {MIN_RELEVANCE})")
        
        # Step 4: Build LLM prompts
        from app.routers.mcp_chat import _build_task_context
        task_context = _build_task_context(relevant_tasks)
        
        system_prompt = """You are a helpful assistant that helps users find and use RunWhen CodeBundles and documentation.

CodeBundles are automation scripts for troubleshooting and managing infrastructure (Kubernetes, AWS, Azure, GCP, databases, etc.).

CRITICAL RULES:
1. ONLY recommend resources that DIRECTLY ADDRESS the user's specific question
2. For "how to" questions about configuration/development, prioritize documentation
3. For troubleshooting/automation questions, recommend relevant codebundles
4. Be STRICT about relevance - fewer accurate recommendations are better than many tangential ones
5. IGNORE results that don't match the user's platform (e.g., don't show Kubernetes results for Azure App Service questions)
6. REMEMBER the conversation history - if the user refers to "this codebundle" or "it", they mean the one discussed previously

When recommending:
- Always use **bold** for CodeBundle names
- Explain what each resource does in plain language
- Mention the SPECIFIC TASKS it contains that are relevant
- Be conversational and keep responses concise but informative

If NO resources directly address the query:
- Start your response with exactly: "[NO_MATCHING_CODEBUNDLE]"
- Be honest: "I couldn't find a codebundle specifically for [user's need]"
- Tell them they can request this automation by clicking the "Request CodeBundle" button below"""
        
        user_prompt = f"""User Question: {question}

Available CodeBundles from search (sorted by relevance score):

{task_context}

IMPORTANT: Only recommend codebundles that DIRECTLY solve the user's problem. 
- If a codebundle doesn't specifically address their question, don't include it
- If none are truly relevant, say so honestly
- Quality over quantity - 1-2 good matches is better than 5 mediocre ones
- If the user is asking a follow-up about a previously mentioned codebundle, answer based on the conversation history"""
        
        logger.info(f"[DEBUG] System prompt length: {len(system_prompt)} chars")
        logger.info(f"[DEBUG] User prompt length: {len(user_prompt)} chars")
        
        # Step 5: Call LLM
        llm_response = ""
        if ai_service.is_enabled():
            try:
                client = ai_service._get_ai_client()
                model_name = ai_service._get_model_name()
                
                messages = [{"role": "system", "content": system_prompt}]
                
                # Add conversation history
                if conversation_history:
                    for msg in conversation_history[-6:]:
                        messages.append({
                            "role": msg.get("role", "user"),
                            "content": msg.get("content", "")
                        })
                
                messages.append({"role": "user", "content": user_prompt})
                
                logger.info(f"[DEBUG] Calling LLM with {len(messages)} messages")
                
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=800,
                    temperature=0.7
                )
                
                llm_response = response.choices[0].message.content.strip()
                logger.info(f"[DEBUG] LLM response length: {len(llm_response)} chars")
                logger.info(f"[DEBUG] LLM response preview: {llm_response[:200]}...")
                
            except Exception as e:
                logger.error(f"[DEBUG] LLM call failed: {e}")
                llm_response = f"[LLM ERROR: {str(e)}]"
        else:
            llm_response = "[AI SERVICE NOT ENABLED]"
            logger.warning("[DEBUG] AI service is not enabled")
        
        # Step 6: Process response
        no_match = "[NO_MATCHING_CODEBUNDLE]" in llm_response
        final_answer = llm_response.replace("[NO_MATCHING_CODEBUNDLE]", "").strip()
        
        logger.info(f"[DEBUG] No match flag: {no_match}")
        
        # Step 7: Create debug entry
        debug_entry = ChatDebugEntry(
            timestamp=datetime.utcnow().isoformat(),
            question=question,
            conversation_history=conversation_history,
            mcp_response=mcp_response,
            relevant_tasks_count=len(relevant_tasks),
            relevant_tasks=[{
                "name": t.codebundle_name,
                "slug": t.codebundle_slug,
                "relevance_score": t.relevance_score,
                "platform": t.platform,
                "description": t.description[:200] if t.description else ""
            } for t in relevant_tasks],
            llm_system_prompt=system_prompt,
            llm_user_prompt=user_prompt,
            llm_response=llm_response,
            final_answer=final_answer,
            no_match_flag=no_match,
            query_metadata={
                "platform_detected": platform,
                "all_tasks_count": len(all_tasks),
                "filtered_tasks_count": len(relevant_tasks),
                "conversation_length": len(conversation_history),
                "ai_enabled": ai_service.is_enabled()
            }
        )
        
        # Store for later analysis
        store_chat_debug(debug_entry)
        
        # Step 8: Analyze and provide recommendations
        analysis = _analyze_debug_entry(debug_entry)
        recommendations = _generate_recommendations(debug_entry, analysis)
        
        return ChatDebugResponse(
            debug_entry=debug_entry,
            analysis=analysis,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"Error in debug test query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _analyze_debug_entry(entry: ChatDebugEntry) -> Dict[str, Any]:
    """Analyze a debug entry to identify potential issues"""
    issues = []
    
    # Check if MCP found results
    if entry.relevant_tasks_count == 0:
        issues.append({
            "type": "no_tasks_found",
            "severity": "high",
            "message": "MCP search returned 0 relevant tasks above threshold"
        })
    elif entry.relevant_tasks_count < 2:
        issues.append({
            "type": "few_tasks_found",
            "severity": "medium",
            "message": f"Only {entry.relevant_tasks_count} task(s) found - may limit LLM options"
        })
    
    # Check relevance scores
    if entry.relevant_tasks:
        max_score = max(t["relevance_score"] for t in entry.relevant_tasks)
        if max_score < 0.65:
            issues.append({
                "type": "low_relevance",
                "severity": "medium",
                "message": f"Highest relevance score is only {max_score:.0%} - semantic match may be weak"
            })
    
    # Check for contradictions
    has_tasks = entry.relevant_tasks_count > 0
    if has_tasks and entry.no_match_flag:
        issues.append({
            "type": "llm_contradiction",
            "severity": "high",
            "message": "LLM said no match despite having relevant tasks - possible prompt issue"
        })
    
    # Check for follow-up issues
    is_followup = len(entry.conversation_history) > 0
    if is_followup and entry.no_match_flag:
        issues.append({
            "type": "followup_failure",
            "severity": "high",
            "message": "Follow-up question resulted in no match - context may be lost"
        })
    
    # Check conversation context
    if is_followup:
        last_user_msg = None
        last_assistant_msg = None
        for msg in reversed(entry.conversation_history):
            if msg["role"] == "user" and not last_user_msg:
                last_user_msg = msg["content"]
            elif msg["role"] == "assistant" and not last_assistant_msg:
                last_assistant_msg = msg["content"]
            if last_user_msg and last_assistant_msg:
                break
        
        analysis_context = {
            "is_followup": True,
            "last_user_question": last_user_msg,
            "last_assistant_answer": last_assistant_msg[:200] if last_assistant_msg else None
        }
    else:
        analysis_context = {"is_followup": False}
    
    return {
        "issues": issues,
        "issue_count": len(issues),
        "severity_summary": {
            "high": sum(1 for i in issues if i["severity"] == "high"),
            "medium": sum(1 for i in issues if i["severity"] == "medium"),
            "low": sum(1 for i in issues if i["severity"] == "low")
        },
        "context": analysis_context
    }


def _generate_recommendations(entry: ChatDebugEntry, analysis: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on the analysis"""
    recommendations = []
    
    for issue in analysis["issues"]:
        if issue["type"] == "no_tasks_found":
            recommendations.append("Consider lowering the MIN_RELEVANCE threshold or improving embeddings quality")
            recommendations.append("Check if the query needs better keyword expansion or synonyms")
        
        elif issue["type"] == "low_relevance":
            recommendations.append("Semantic search may need tuning - check embedding model and vector database")
            recommendations.append("Consider adding more metadata tags to codebundles for better matching")
        
        elif issue["type"] == "llm_contradiction":
            recommendations.append("Review LLM system prompt - it may be too strict about relevance")
            recommendations.append("Check if task descriptions in context are clear and relevant")
            recommendations.append("Consider adjusting LLM temperature or max_tokens")
        
        elif issue["type"] == "followup_failure":
            recommendations.append("Improve conversation context handling - ensure previous codebundles are preserved")
            recommendations.append("Check if followup detection logic is working correctly")
            recommendations.append("Verify that conversation history is being passed to LLM properly")
    
    if not recommendations:
        recommendations.append("No major issues detected - response quality looks good")
    
    return list(set(recommendations))  # Remove duplicates


def _generate_quality_recommendations(stats: Dict[str, float]) -> List[str]:
    """Generate recommendations based on overall quality stats"""
    recommendations = []
    
    if stats["no_match_rate"] > 0.3:  # >30% no-match rate
        recommendations.append("HIGH no-match rate detected - review semantic search relevance thresholds")
        recommendations.append("Consider expanding codebundle metadata and descriptions")
    
    if stats.get("followup_no_match_rate", 0) > 0.4:  # >40% followup failures
        recommendations.append("Follow-up questions are failing frequently - improve conversation context handling")
        recommendations.append("Review followup detection logic in mcp_chat.py")
    
    if stats["avg_tasks"] < 2:
        recommendations.append("Low average task count - may need to lower relevance threshold or improve search")
    
    if not recommendations:
        recommendations.append("Chat quality metrics look healthy")
    
    return recommendations


@router.delete("/clear-history")
async def clear_chat_history():
    """Clear the in-memory chat history (for testing/debugging)"""
    global recent_chats
    count = len(recent_chats)
    recent_chats = []
    return {
        "status": "success",
        "message": f"Cleared {count} chat entries from debug history"
    }
