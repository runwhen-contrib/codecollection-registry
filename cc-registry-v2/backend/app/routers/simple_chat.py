"""
Simple Chat Router for testing - minimal implementation
"""
import logging
from typing import Dict, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Codebundle, CodeCollection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/simple-chat", tags=["simple-chat"])


class SimpleChatQuery(BaseModel):
    question: str


class SimpleChatResponse(BaseModel):
    answer: str
    relevant_codebundles: List[Dict]


@router.post("/query", response_model=SimpleChatResponse)
async def simple_query(
    query: SimpleChatQuery,
    db: Session = Depends(get_db)
):
    """Simple chat query for testing"""
    try:
        # Find codebundles that match the query
        search_term = f"%{query.question.lower()}%"
        
        codebundles = db.query(Codebundle).join(CodeCollection).filter(
            Codebundle.is_active == True
        ).filter(
            # Search in various fields
            (Codebundle.name.ilike(search_term)) |
            (Codebundle.display_name.ilike(search_term)) |
            (Codebundle.description.ilike(search_term))
        ).limit(3).all()
        
        # Format results
        relevant_codebundles = []
        for cb in codebundles:
            relevant_codebundles.append({
                "name": cb.display_name or cb.name,
                "description": cb.description or "No description available",
                "collection": cb.codecollection.name if cb.codecollection else "Unknown",
                "support_tags": cb.support_tags or []
            })
        
        # Generate simple answer
        if relevant_codebundles:
            answer = f"I found {len(relevant_codebundles)} relevant codebundles for your question '{query.question}':\n\n"
            for i, cb in enumerate(relevant_codebundles, 1):
                answer += f"{i}. **{cb['name']}** (from {cb['collection']})\n"
                if cb['description'] and cb['description'] != "No description available":
                    answer += f"   {cb['description']}\n"
                if cb['support_tags']:
                    answer += f"   Tags: {', '.join(cb['support_tags'])}\n"
                answer += "\n"
            
            # Add helpful context about what these codebundles contain
            if query.question.lower() in ['sli', 'slis']:
                answer += "**Note:** SLI (Service Level Indicator) codebundles contain monitoring and measurement tasks to track service performance metrics.\n"
            elif query.question.lower() in ['runbook', 'runbooks']:
                answer += "**Note:** Runbook codebundles contain operational procedures and troubleshooting tasks.\n"
            elif any(word in query.question.lower() for word in ['pod', 'pods', 'kubernetes', 'k8s']):
                answer += "**Note:** Look for Kubernetes-related codebundles that contain pod troubleshooting and management tasks.\n"
        else:
            # Suggest adding to registry and provide helpful suggestions
            answer = f"I couldn't find any codebundles matching your question '{query.question}'. \n\n"
            answer += "**Would you like these tasks added to the registry?**\n\n"
            answer += f"If you need tasks for '{query.question}', we can add them to the CodeCollection registry.\n"
            answer += "You can create a GitHub issue to request these tasks.\n\n"
            answer += "**Or try searching for existing tasks:**\n"
            answer += "• 'sli' - for monitoring and measurement tasks\n"
            answer += "• 'runbook' - for operational procedures\n"
            answer += "• 'kubernetes' or 'k8s' - for container orchestration tasks\n"
            answer += "• 'azure', 'aws', 'gcp' - for cloud platform specific tasks\n"
            answer += "• 'cli' - for command-line interface tools\n"
        
        return SimpleChatResponse(
            answer=answer,
            relevant_codebundles=relevant_codebundles
        )
        
    except Exception as e:
        logger.error(f"Error in simple chat: {e}", exc_info=True)
        return SimpleChatResponse(
            answer=f"Sorry, I encountered an error: {str(e)}",
            relevant_codebundles=[]
        )


@router.get("/test")
async def test_endpoint():
    """Test endpoint"""
    return {"status": "working", "message": "Simple chat is operational"}
