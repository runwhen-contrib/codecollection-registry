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
    readme = Column(Text)  # README.md content
    
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
    tasks = Column(JSON, default=list)  # List of task names (backward compatibility)
    slis = Column(JSON, default=list)    # List of SLI names
    task_count = Column(Integer, default=0)
    sli_count = Column(Integer, default=0)
    
    # User variables parsed from RW.Core.Import User Variable
    user_variables = Column(JSON, default=list)  # List of {name, type, description, pattern, example, default}
    
    # Enhanced task indexing and AI metadata
    task_index = Column(JSON, default=dict)  # {"task_name": "unique_index", ...}
    ai_enhanced_metadata = Column(JSON, default=dict)  # AI-generated enhancements
    enhancement_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    last_enhanced = Column(DateTime)
    
    # AI-enhanced fields
    ai_enhanced_description = Column(Text)  # AI-generated improved description
    access_level = Column(String(20), default="unknown")  # read-only, read-write, unknown
    minimum_iam_requirements = Column(JSON, default=list)  # List of required IAM permissions/roles
    
    # Generation metadata
    has_genrules = Column(Boolean, default=False)
    found_in_cheatsheet = Column(Boolean, default=False)
    raises_issues = Column(Boolean, default=False)
    
    # Discovery configuration
    is_discoverable = Column(Boolean, default=False)
    discovery_platform = Column(String(100))  # e.g., "aws", "kubernetes", "gcp"
    discovery_resource_types = Column(JSON, default=list)  # e.g., ["aws_eks_clusters"]
    discovery_match_patterns = Column(JSON, default=list)  # Match rules from generation-rules
    discovery_templates = Column(JSON, default=list)  # Available template files
    discovery_output_items = Column(JSON, default=list)  # Types: slx, sli, runbook
    discovery_level_of_detail = Column(String(50))  # e.g., "basic", "detailed"
    runwhen_directory_path = Column(String(500))  # Path to .runwhen directory
    
    # Status and timestamps
    is_active = Column(Boolean, default=True)
    last_synced = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    git_updated_at = Column(DateTime)  # Last commit date from git for the codebundle folder
    
    # Relationships
    codecollection = relationship("CodeCollection", back_populates="codebundles")
    
    def __repr__(self):
        return f"<Codebundle(id={self.id}, name='{self.name}', slug='{self.slug}')>"
