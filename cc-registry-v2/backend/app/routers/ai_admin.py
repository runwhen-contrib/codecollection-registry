"""
Admin API endpoints for AI configuration and enhancement management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models import AIConfiguration, Codebundle
from app.tasks.ai_enhancement_tasks import (
    enhance_codebundle_task,
    enhance_multiple_codebundles_task,
    enhance_collection_codebundles_task,
    enhance_pending_codebundles_task
)
from celery.result import AsyncResult
from app.services.task_monitoring_service import task_monitor

# Simple token-based auth for now
security = HTTPBearer()

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin token - in production, use proper JWT or OAuth"""
    if not credentials.credentials.startswith('admin-'):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return credentials.credentials

router = APIRouter(prefix="/api/v1/admin/ai", tags=["ai-admin"])


# Pydantic models for API
class AIConfigCreate(BaseModel):
    service_provider: str = "openai"
    api_key: str
    model_name: str = "gpt-4"
    enhancement_enabled: bool = True
    auto_enhance_new_bundles: bool = False
    max_requests_per_hour: int = 100
    max_concurrent_requests: int = 5
    enhancement_prompt_template: Optional[str] = None
    # Azure OpenAI specific fields
    azure_endpoint: Optional[str] = None
    azure_deployment_name: Optional[str] = None
    api_version: Optional[str] = "2024-02-15-preview"


class AIConfigUpdate(BaseModel):
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    enhancement_enabled: Optional[bool] = None
    auto_enhance_new_bundles: Optional[bool] = None
    max_requests_per_hour: Optional[int] = None
    max_concurrent_requests: Optional[int] = None
    enhancement_prompt_template: Optional[str] = None
    # Azure OpenAI specific fields
    azure_endpoint: Optional[str] = None
    azure_deployment_name: Optional[str] = None
    api_version: Optional[str] = None


class AIConfigResponse(BaseModel):
    id: int
    service_provider: str
    model_name: str
    enhancement_enabled: bool
    auto_enhance_new_bundles: bool
    max_requests_per_hour: int
    max_concurrent_requests: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Azure OpenAI specific fields
    azure_endpoint: Optional[str] = None
    azure_deployment_name: Optional[str] = None
    api_version: Optional[str] = None
    
    class Config:
        from_attributes = True


class EnhancementRequest(BaseModel):
    codebundle_ids: Optional[List[int]] = None
    collection_slug: Optional[str] = None
    enhance_pending: bool = False
    limit: Optional[int] = None


@router.get("/config", response_model=List[AIConfigResponse])
async def get_ai_configurations(
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get all AI configurations"""
    configs = db.query(AIConfiguration).all()
    return configs


@router.get("/config/active", response_model=Optional[AIConfigResponse])
async def get_active_ai_configuration(
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get the active AI configuration"""
    config = db.query(AIConfiguration).filter(
        AIConfiguration.is_active == True
    ).first()
    return config


@router.post("/config", response_model=AIConfigResponse)
async def create_ai_configuration(
    config_data: AIConfigCreate,
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Create a new AI configuration"""
    
    # Deactivate existing configs if this one is being set as active
    if config_data.enhancement_enabled:
        db.query(AIConfiguration).update({"is_active": False})
    
    config = AIConfiguration(
        service_provider=config_data.service_provider,
        api_key=config_data.api_key,  # In production, encrypt this
        model_name=config_data.model_name,
        enhancement_enabled=config_data.enhancement_enabled,
        auto_enhance_new_bundles=config_data.auto_enhance_new_bundles,
        max_requests_per_hour=config_data.max_requests_per_hour,
        max_concurrent_requests=config_data.max_concurrent_requests,
        enhancement_prompt_template=config_data.enhancement_prompt_template,
        # Azure OpenAI specific fields
        azure_endpoint=config_data.azure_endpoint,
        azure_deployment_name=config_data.azure_deployment_name,
        api_version=config_data.api_version,
        created_by=token,  # In production, use actual user ID
        is_active=config_data.enhancement_enabled
    )
    
    db.add(config)
    db.commit()
    db.refresh(config)
    
    return config


@router.put("/config/{config_id}", response_model=AIConfigResponse)
async def update_ai_configuration(
    config_id: int,
    config_data: AIConfigUpdate,
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Update an AI configuration"""
    
    config = db.query(AIConfiguration).filter(AIConfiguration.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="AI configuration not found")
    
    # Update fields
    update_data = config_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    
    # If enabling this config, deactivate others
    if config_data.enhancement_enabled:
        db.query(AIConfiguration).filter(AIConfiguration.id != config_id).update({"is_active": False})
        config.is_active = True
    
    config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(config)
    
    return config


@router.delete("/config/{config_id}")
async def delete_ai_configuration(
    config_id: int,
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Delete an AI configuration"""
    
    config = db.query(AIConfiguration).filter(AIConfiguration.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="AI configuration not found")
    
    db.delete(config)
    db.commit()
    
    return {"message": "AI configuration deleted successfully"}


@router.post("/reset")
async def reset_ai_enhancements(
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Reset all AI enhancement data - sets all CodeBundles back to pending status"""
    try:
        # Reset all CodeBundles to pending status and clear AI data
        updated_count = db.query(Codebundle).filter(
            Codebundle.is_active == True
        ).update({
            Codebundle.enhancement_status: "pending",
            Codebundle.ai_enhanced_description: None,
            Codebundle.access_level: None,
            Codebundle.minimum_iam_requirements: None,
            Codebundle.ai_enhanced_metadata: None,
            Codebundle.last_enhanced: None
        })
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Reset AI enhancement data for {updated_count} CodeBundles",
            "reset_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Error resetting AI enhancements: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset AI enhancements: {str(e)}"
        )


@router.post("/enhance")
async def trigger_ai_enhancement(
    request: EnhancementRequest,
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Trigger AI enhancement for CodeBundles"""
    
    # Check if AI is configured
    config = db.query(AIConfiguration).filter(
        AIConfiguration.is_active == True,
        AIConfiguration.enhancement_enabled == True
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=400, 
            detail="AI enhancement is not enabled or configured"
        )
    
    task_result = None
    
    if request.enhance_pending:
        # Enhance all pending CodeBundles
        task_result = enhance_pending_codebundles_task.delay(request.limit)
        
        # Create task record for monitoring
        task_monitor.create_task_record(
            task_id=task_result.id,
            task_name="AI Enhancement - Pending CodeBundles",
            task_type="ai_enhancement",
            parameters={"enhance_pending": True, "limit": request.limit},
            triggered_by=token
        )
        
    elif request.collection_slug:
        # Enhance all CodeBundles in a collection
        task_result = enhance_collection_codebundles_task.delay(request.collection_slug)
        
        # Create task record for monitoring
        task_monitor.create_task_record(
            task_id=task_result.id,
            task_name=f"AI Enhancement - Collection {request.collection_slug}",
            task_type="ai_enhancement",
            parameters={"collection_slug": request.collection_slug},
            triggered_by=token
        )
        
    elif request.codebundle_ids:
        # Enhance specific CodeBundles
        if len(request.codebundle_ids) == 1:
            task_result = enhance_codebundle_task.delay(request.codebundle_ids[0])
            
            # Create task record for monitoring
            task_monitor.create_task_record(
                task_id=task_result.id,
                task_name=f"AI Enhancement - CodeBundle {request.codebundle_ids[0]}",
                task_type="ai_enhancement",
                parameters={"codebundle_ids": request.codebundle_ids},
                triggered_by=token
            )
        else:
            task_result = enhance_multiple_codebundles_task.delay(request.codebundle_ids)
            
            # Create task record for monitoring
            task_monitor.create_task_record(
                task_id=task_result.id,
                task_name=f"AI Enhancement - {len(request.codebundle_ids)} CodeBundles",
                task_type="ai_enhancement",
                parameters={"codebundle_ids": request.codebundle_ids},
                triggered_by=token
            )
    
    else:
        raise HTTPException(
            status_code=400,
            detail="Must specify codebundle_ids, collection_slug, or enhance_pending=True"
        )
    
    return {
        "task_id": task_result.id,
        "status": "started",
        "message": "AI enhancement task started"
    }


@router.get("/enhance/status/{task_id}")
async def get_enhancement_status(
    task_id: str,
    token: str = Depends(verify_admin_token)
):
    """Get the status of an AI enhancement task"""
    
    result = AsyncResult(task_id)
    
    if result.state == 'PENDING':
        response = {
            'task_id': task_id,
            'state': result.state,
            'status': 'Task is waiting to be processed'
        }
    elif result.state == 'PROGRESS':
        response = {
            'task_id': task_id,
            'state': result.state,
            'current': result.info.get('current', 0),
            'total': result.info.get('total', 1),
            'status': result.info.get('status', '')
        }
    elif result.state == 'SUCCESS':
        response = {
            'task_id': task_id,
            'state': result.state,
            'result': result.result
        }
    else:  # FAILURE
        response = {
            'task_id': task_id,
            'state': result.state,
            'error': str(result.info)
        }
    
    return response


@router.get("/stats")
async def get_enhancement_stats(
    token: str = Depends(verify_admin_token),
    db: Session = Depends(get_db)
):
    """Get AI enhancement statistics"""
    
    total_codebundles = db.query(Codebundle).filter(Codebundle.is_active == True).count()
    
    pending = db.query(Codebundle).filter(
        (Codebundle.enhancement_status == "pending") | (Codebundle.enhancement_status.is_(None)),
        Codebundle.is_active == True
    ).count()
    
    processing = db.query(Codebundle).filter(
        Codebundle.enhancement_status == "processing",
        Codebundle.is_active == True
    ).count()
    
    completed = db.query(Codebundle).filter(
        Codebundle.enhancement_status == "completed",
        Codebundle.is_active == True
    ).count()
    
    failed = db.query(Codebundle).filter(
        Codebundle.enhancement_status == "failed",
        Codebundle.is_active == True
    ).count()
    
    # Access level stats
    read_only = db.query(Codebundle).filter(
        Codebundle.access_level == "read-only",
        Codebundle.is_active == True
    ).count()
    
    read_write = db.query(Codebundle).filter(
        Codebundle.access_level == "read-write",
        Codebundle.is_active == True
    ).count()
    
    return {
        "total_codebundles": total_codebundles,
        "enhancement_status": {
            "pending": pending,
            "processing": processing,
            "completed": completed,
            "failed": failed
        },
        "access_levels": {
            "read_only": read_only,
            "read_write": read_write,
            "unknown": total_codebundles - read_only - read_write
        },
        "completion_rate": round((completed / total_codebundles * 100), 2) if total_codebundles > 0 else 0
    }

