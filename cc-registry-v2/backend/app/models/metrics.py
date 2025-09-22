from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class CodeCollectionMetrics(Base):
    """Track metrics for CodeCollections over time"""
    __tablename__ = "codecollection_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    codecollection_id = Column(Integer, ForeignKey("codecollections.id"), nullable=False)
    
    # Counts
    codebundle_count = Column(Integer, default=0)
    total_task_count = Column(Integer, default=0)
    total_sli_count = Column(Integer, default=0)
    
    # Enhancement status counts
    enhanced_codebundles = Column(Integer, default=0)
    pending_enhancements = Column(Integer, default=0)
    failed_enhancements = Column(Integer, default=0)
    
    # Additional metrics
    avg_tasks_per_codebundle = Column(Integer, default=0)
    most_common_categories = Column(JSON, default=list)
    
    # Timestamps
    snapshot_date = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    codecollection = relationship("CodeCollection")
    
    def __repr__(self):
        return f"<CodeCollectionMetrics(collection_id={self.codecollection_id}, date={self.snapshot_date})>"


class SystemMetrics(Base):
    """Track overall system metrics over time"""
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Overall counts
    total_collections = Column(Integer, default=0)
    total_codebundles = Column(Integer, default=0)
    total_tasks = Column(Integer, default=0)
    total_slis = Column(Integer, default=0)
    
    # Processing status
    collections_synced_today = Column(Integer, default=0)
    codebundles_parsed_today = Column(Integer, default=0)
    enhancements_processed_today = Column(Integer, default=0)
    
    # Performance metrics
    avg_sync_time_minutes = Column(Integer, default=0)
    avg_parse_time_minutes = Column(Integer, default=0)
    avg_enhancement_time_minutes = Column(Integer, default=0)
    
    # Timestamps
    snapshot_date = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<SystemMetrics(date={self.snapshot_date}, collections={self.total_collections})>"
