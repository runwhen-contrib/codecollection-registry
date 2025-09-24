from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, Float
from sqlalchemy.sql import func
from datetime import datetime
from app.core.database import Base


class TaskExecution(Base):
    """Store task execution history and status"""
    __tablename__ = "task_executions"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(255), nullable=False, unique=True, index=True)  # Celery task ID
    task_name = Column(String(255), nullable=False, index=True)  # Human-readable task name
    task_type = Column(String(100), nullable=False, index=True)  # Task category/type
    
    # Status tracking
    status = Column(String(50), nullable=False, default="PENDING", index=True)  # PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
    progress = Column(Float, default=0.0)  # 0.0 to 100.0
    current_step = Column(String(255))  # Current processing step
    
    # Execution details
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Float)  # Total execution time
    
    # Results and errors
    result = Column(JSON)  # Task result data
    error_message = Column(Text)  # Error details if failed
    traceback = Column(Text)  # Full error traceback
    
    # Metadata
    triggered_by = Column(String(255))  # User or system that triggered the task
    parameters = Column(JSON)  # Task parameters/arguments
    worker_name = Column(String(255))  # Celery worker that executed the task
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<TaskExecution(id={self.id}, task_id='{self.task_id}', task_name='{self.task_name}', status='{self.status}')>"
    
    @property
    def is_running(self) -> bool:
        return self.status in ['PENDING', 'STARTED']
    
    @property
    def is_completed(self) -> bool:
        return self.status in ['SUCCESS', 'FAILURE', 'REVOKED']
    
    @property
    def is_successful(self) -> bool:
        return self.status == 'SUCCESS'
    
    @property
    def is_failed(self) -> bool:
        return self.status in ['FAILURE', 'REVOKED']

