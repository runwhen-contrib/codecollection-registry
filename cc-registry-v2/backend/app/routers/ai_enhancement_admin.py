"""
AI Enhancement Administration API
Provides full control and visibility over AI enhancement process
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models import Codebundle
from app.models.ai_enhancement_log import AIEnhancementLog
from app.services.enhanced_ai_service import get_enhanced_ai_service

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials

router = APIRouter(prefix="/admin/ai-enhancement", tags=["AI Enhancement Admin"])


class EnhancementLogResponse(BaseModel):
    id: int
    codebundle_id: int
    codebundle_slug: str
    status: str
    model_used: str
    service_provider: str
    prompt_sent: Optional[str]
    system_prompt: Optional[str]
    ai_response_raw: Optional[str]
    enhanced_description: Optional[str]
    access_level: Optional[str]
    iam_requirements: Optional[List[str]]
    error_message: Optional[str]
    processing_time_ms: Optional[int]
    is_manually_edited: bool
    manual_notes: Optional[str]
    created_at: str
    updated_at: Optional[str]


class ManualEditRequest(BaseModel):
    enhanced_description: str
    access_level: str
    iam_requirements: List[str]
    manual_notes: Optional[str] = None


class PromptEditRequest(BaseModel):
    system_prompt: str
    user_prompt: str


@router.get("/logs", response_model=List[EnhancementLogResponse])
async def get_enhancement_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None),
    codebundle_slug: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Get AI enhancement logs with filtering"""
    
    query = db.query(AIEnhancementLog)
    
    if status:
        query = query.filter(AIEnhancementLog.status == status)
    
    if codebundle_slug:
        query = query.filter(AIEnhancementLog.codebundle_slug.like(f"%{codebundle_slug}%"))
    
    logs = query.order_by(AIEnhancementLog.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        EnhancementLogResponse(
            id=log.id,
            codebundle_id=log.codebundle_id,
            codebundle_slug=log.codebundle_slug,
            status=log.status,
            model_used=log.model_used,
            service_provider=log.service_provider,
            prompt_sent=log.prompt_sent,
            system_prompt=log.system_prompt,
            ai_response_raw=log.ai_response_raw,
            enhanced_description=log.enhanced_description,
            access_level=log.access_level,
            iam_requirements=log.iam_requirements,
            error_message=log.error_message,
            processing_time_ms=log.processing_time_ms,
            is_manually_edited=log.is_manually_edited,
            manual_notes=log.manual_notes,
            created_at=log.created_at.isoformat(),
            updated_at=log.updated_at.isoformat() if log.updated_at else None
        )
        for log in logs
    ]


@router.get("/logs/{log_id}", response_model=EnhancementLogResponse)
async def get_enhancement_log(
    log_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Get specific enhancement log with full details"""
    
    log = db.query(AIEnhancementLog).filter(AIEnhancementLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Enhancement log not found")
    
    return EnhancementLogResponse(
        id=log.id,
        codebundle_id=log.codebundle_id,
        codebundle_slug=log.codebundle_slug,
        status=log.status,
        model_used=log.model_used,
        service_provider=log.service_provider,
        prompt_sent=log.prompt_sent,
        system_prompt=log.system_prompt,
        ai_response_raw=log.ai_response_raw,
        enhanced_description=log.enhanced_description,
        access_level=log.access_level,
        iam_requirements=log.iam_requirements,
        error_message=log.error_message,
        processing_time_ms=log.processing_time_ms,
        is_manually_edited=log.is_manually_edited,
        manual_notes=log.manual_notes,
        created_at=log.created_at.isoformat(),
        updated_at=log.updated_at.isoformat() if log.updated_at else None
    )


@router.put("/logs/{log_id}/manual-edit")
async def manually_edit_enhancement(
    log_id: int,
    edit_request: ManualEditRequest,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Manually edit an enhancement result"""
    
    log = db.query(AIEnhancementLog).filter(AIEnhancementLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Enhancement log not found")
    
    # Update the log with manual edits
    log.enhanced_description = edit_request.enhanced_description
    log.access_level = edit_request.access_level
    log.iam_requirements = edit_request.iam_requirements
    log.is_manually_edited = True
    log.manual_notes = edit_request.manual_notes
    log.status = 'manual_override'
    
    # Update the actual codebundle
    codebundle = db.query(Codebundle).filter(Codebundle.id == log.codebundle_id).first()
    if codebundle:
        codebundle.ai_enhanced_description = edit_request.enhanced_description
        codebundle.access_level = edit_request.access_level
        codebundle.minimum_iam_requirements = edit_request.iam_requirements
        
        # Update metadata to reflect manual edit
        if codebundle.ai_enhanced_metadata:
            metadata = codebundle.ai_enhanced_metadata
        else:
            metadata = {}
        
        metadata.update({
            "manually_edited": True,
            "manual_edit_at": log.updated_at.isoformat() if log.updated_at else None,
            "log_id": log.id
        })
        codebundle.ai_enhanced_metadata = metadata
    
    db.commit()
    
    return {"message": "Enhancement manually edited successfully", "log_id": log.id}


@router.post("/test-prompt/{codebundle_id}")
async def test_prompt_for_codebundle(
    codebundle_id: int,
    prompt_request: PromptEditRequest,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Test a custom prompt on a specific codebundle without saving results"""
    
    codebundle = db.query(Codebundle).filter(Codebundle.id == codebundle_id).first()
    if not codebundle:
        raise HTTPException(status_code=404, detail="Codebundle not found")
    
    ai_service = get_enhanced_ai_service(db)
    if not ai_service or not ai_service.is_enabled():
        raise HTTPException(status_code=400, detail="AI service not available")
    
    try:
        # Prepare context
        context = ai_service._prepare_comprehensive_context(codebundle)
        
        # Use custom prompts
        client = ai_service._get_ai_client()
        
        response = client.chat.completions.create(
            model=ai_service._get_model_name(),
            messages=[
                {"role": "system", "content": prompt_request.system_prompt},
                {"role": "user", "content": prompt_request.user_prompt}
            ],
            max_tokens=1500,
            temperature=0.3
        )
        
        raw_response = response.choices[0].message.content.strip()
        
        return {
            "codebundle_slug": codebundle.slug,
            "context_used": {
                "name": context.get('name'),
                "platform": context.get('platform'),
                "task_count": context.get('task_count'),
                "has_robot_content": context.get('has_robot_content'),
                "file_count": context.get('file_count')
            },
            "prompts_sent": {
                "system_prompt": prompt_request.system_prompt,
                "user_prompt": prompt_request.user_prompt
            },
            "ai_response": raw_response,
            "model_used": ai_service._get_model_name(),
            "service_provider": ai_service.config.service_provider
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI API call failed: {str(e)}")


@router.get("/codebundle/{codebundle_id}/context")
async def get_codebundle_context(
    codebundle_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Get the full context that would be sent to AI for a codebundle"""
    
    codebundle = db.query(Codebundle).filter(Codebundle.id == codebundle_id).first()
    if not codebundle:
        raise HTTPException(status_code=404, detail="Codebundle not found")
    
    ai_service = get_enhanced_ai_service(db)
    if not ai_service:
        raise HTTPException(status_code=400, detail="AI service not available")
    
    context = ai_service._prepare_comprehensive_context(codebundle)
    prompt = ai_service._generate_comprehensive_prompt(context)
    
    return {
        "codebundle_slug": codebundle.slug,
        "context": context,
        "generated_prompt": prompt,
        "prompt_length": len(prompt),
        "has_robot_content": bool(context.get('robot_content')),
        "task_count": len(context.get('actual_tasks', [])),
        "file_count": len(context.get('related_files', []))
    }


@router.post("/enhance/{codebundle_id}")
async def enhance_single_codebundle(
    codebundle_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Enhance a single codebundle with full logging"""
    
    codebundle = db.query(Codebundle).filter(Codebundle.id == codebundle_id).first()
    if not codebundle:
        raise HTTPException(status_code=404, detail="Codebundle not found")
    
    ai_service = get_enhanced_ai_service(db)
    if not ai_service or not ai_service.is_enabled():
        raise HTTPException(status_code=400, detail="AI service not available")
    
    try:
        result = ai_service.enhance_codebundle_with_logging(codebundle)
        
        # Update codebundle
        codebundle.ai_enhanced_description = result["enhanced_description"]
        codebundle.access_level = result["access_level"]
        codebundle.minimum_iam_requirements = result["iam_requirements"]
        codebundle.ai_enhanced_metadata = result["enhancement_metadata"]
        codebundle.enhancement_status = "completed"
        
        db.commit()
        
        return {
            "message": "Codebundle enhanced successfully",
            "codebundle_slug": codebundle.slug,
            "log_id": result["enhancement_metadata"]["log_id"],
            "result": result
        }
        
    except Exception as e:
        codebundle.enhancement_status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Enhancement failed: {str(e)}")


@router.get("/stats")
async def get_enhancement_stats(
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Get AI enhancement statistics"""
    
    total_logs = db.query(AIEnhancementLog).count()
    successful = db.query(AIEnhancementLog).filter(AIEnhancementLog.status == 'success').count()
    failed = db.query(AIEnhancementLog).filter(AIEnhancementLog.status == 'failed').count()
    manual_edits = db.query(AIEnhancementLog).filter(AIEnhancementLog.is_manually_edited == True).count()
    
    # Average processing time
    avg_time = db.query(AIEnhancementLog.processing_time_ms).filter(
        AIEnhancementLog.processing_time_ms.isnot(None)
    ).all()
    
    avg_processing_time = sum(t[0] for t in avg_time) / len(avg_time) if avg_time else 0
    
    return {
        "total_enhancements": total_logs,
        "successful": successful,
        "failed": failed,
        "manual_edits": manual_edits,
        "success_rate": (successful / total_logs * 100) if total_logs > 0 else 0,
        "average_processing_time_ms": int(avg_processing_time)
    }
