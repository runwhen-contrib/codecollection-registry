"""
Chat Router for CodeCollection Query System
Provides AI-powered question answering about codecollection tasks and libraries
"""
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.ai_service import AIEnhancementService
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatQuery(BaseModel):
    """Request model for chat queries"""
    question: str
    context_limit: Optional[int] = 10  # Number of relevant tasks to include in context
    include_enhanced_descriptions: Optional[bool] = True


class ChatResponse(BaseModel):
    """Response model for chat queries"""
    answer: str
    relevant_tasks: List[Dict]
    confidence_score: Optional[float] = None
    sources_used: List[str]
    query_metadata: Dict


@router.post("/query", response_model=ChatResponse)
async def query_codecollections(
    query: ChatQuery,
    db: Session = Depends(get_db)
):
    """
    Answer questions about codecollection tasks and libraries using AI
    
    Examples:
    - "What do I run when pods are failing?"
    - "Which library is useful for running CLI commands?"
    - "How do I debug Azure App Service issues?"
    """
    try:
        # Initialize chat service
        chat_service = ChatService(db)
        
        # Check if AI is enabled
        if not chat_service.is_enabled():
            raise HTTPException(
                status_code=503,
                detail="AI chat service is not enabled or configured. Please check AI configuration."
            )
        
        # Process the query
        try:
            result = await chat_service.answer_query(
                question=query.question,
                context_limit=query.context_limit,
                include_enhanced_descriptions=query.include_enhanced_descriptions
            )
        except Exception as inner_e:
            logger.error(f"Inner error in chat_service.answer_query: {inner_e}", exc_info=True)
            raise inner_e
        
        return ChatResponse(
            answer=result["answer"],
            relevant_tasks=result["relevant_tasks"],
            confidence_score=result.get("confidence_score"),
            sources_used=result["sources_used"],
            query_metadata=result["metadata"]
        )
        
    except Exception as e:
        logger.error(f"Error processing chat query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e) if str(e) else 'Unknown error occurred'}"
        )


@router.get("/health")
async def chat_health_check(db: Session = Depends(get_db)):
    """Check if chat service is available and configured"""
    try:
        chat_service = ChatService(db)
        ai_service = AIEnhancementService(db)
        
        return {
            "status": "healthy" if chat_service.is_enabled() else "disabled",
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
                    "What tasks help with Azure App Service problems?",
                    "How do I troubleshoot AWS EKS cluster issues?"
                ]
            },
            {
                "category": "Libraries & Tools",
                "queries": [
                    "Which library is useful for running CLI commands?",
                    "What tools are available for Kubernetes management?",
                    "How do I use the AWS CLI tools in codebundles?",
                    "What Python libraries are commonly used?"
                ]
            },
            {
                "category": "Platform-Specific",
                "queries": [
                    "What Azure-specific tasks are available?",
                    "How do I work with GCP resources?",
                    "What Kubernetes monitoring tools can I use?",
                    "How do I manage Docker containers?"
                ]
            },
            {
                "category": "General",
                "queries": [
                    "What are the most commonly used codebundles?",
                    "How do I find tasks for monitoring?",
                    "What read-only diagnostic tasks are available?",
                    "Show me tasks that require minimal permissions"
                ]
            }
        ]
    }
