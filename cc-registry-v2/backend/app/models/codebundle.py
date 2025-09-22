from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Codebundle(Base):
    __tablename__ = "codebundles"
    
    id = Column(Integer, primary_key=True, index=True)
    codecollection_id = Column(Integer, ForeignKey("codecollections.id"), nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255))
    description = Column(Text)
    doc = Column(Text)  # Robot file documentation
    
    # Robot file metadata
    author = Column(String(255))
    support_tags = Column(JSON, default=list)  # Tags from Robot file
    categories = Column(JSON, default=list)  # Categorized tags
    
    # File paths and URLs
    runbook_path = Column(String(500))
    sli_path = Column(String(500))
    meta_path = Column(String(500))
    runbook_source_url = Column(String(500))
    
    # Task and SLI data
    tasks = Column(JSON, default=list)  # List of task names
    slis = Column(JSON, default=list)    # List of SLI names
    task_count = Column(Integer, default=0)
    sli_count = Column(Integer, default=0)
    
    # Enhanced task indexing and AI metadata
    task_index = Column(JSON, default=dict)  # {"task_name": "unique_index", ...}
    ai_enhanced_metadata = Column(JSON, default=dict)  # AI-generated enhancements
    enhancement_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    last_enhanced = Column(DateTime)
    
    # Generation metadata
    has_genrules = Column(Boolean, default=False)
    found_in_cheatsheet = Column(Boolean, default=False)
    raises_issues = Column(Boolean, default=False)
    
    # Status and timestamps
    is_active = Column(Boolean, default=True)
    last_synced = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    codecollection = relationship("CodeCollection", back_populates="codebundles")
    
    def __repr__(self):
        return f"<Codebundle(id={self.id}, name='{self.name}', slug='{self.slug}')>"
