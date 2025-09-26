"""
AI Enhancement Logging Model
Tracks all AI enhancement requests and responses for debugging and editing
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class AIEnhancementLog(Base):
    """Log of all AI enhancement requests and responses"""
    __tablename__ = "ai_enhancement_logs"

    id = Column(Integer, primary_key=True, index=True)
    codebundle_id = Column(Integer, index=True)
    codebundle_slug = Column(String(255), index=True)
    
    # Request details
    prompt_sent = Column(Text)  # The actual prompt sent to AI
    system_prompt = Column(Text)  # The system prompt used
    model_used = Column(String(100))
    service_provider = Column(String(50))
    
    # Response details
    ai_response_raw = Column(Text)  # Raw AI response
    ai_response_parsed = Column(JSON)  # Parsed JSON response
    
    # Enhancement results
    enhanced_description = Column(Text)
    access_level = Column(String(20))
    iam_requirements = Column(JSON)
    
    # Status tracking
    status = Column(String(20))  # 'pending', 'success', 'failed', 'manual_override'
    error_message = Column(Text)
    
    # Metadata
    processing_time_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Manual editing support
    is_manually_edited = Column(Boolean, default=False)
    manual_notes = Column(Text)
