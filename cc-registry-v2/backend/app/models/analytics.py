"""
Analytics data models for caching computed metrics
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from sqlalchemy.sql import func
from app.core.database import Base


class TaskGrowthMetric(Base):
    """
    Cached task growth analytics data.
    Computed by background job, served to frontend.
    """
    __tablename__ = "task_growth_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_type = Column(String(50), nullable=False, index=True, default="monthly_growth")
    time_period = Column(String(20), nullable=False)  # e.g., "18_months", "all_time"
    
    # JSON data: { "months": [...], "cumulative": [...], "total_tasks": 123 }
    data = Column(JSON, nullable=False)
    
    # Metadata
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    computation_duration_seconds = Column(Integer)
    codebundles_analyzed = Column(Integer)
    notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
