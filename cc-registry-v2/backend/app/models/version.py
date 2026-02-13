from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class CodeCollectionVersion(Base):
    """
    Represents a version of a CodeCollection.
    Each version can point to a git tag, branch, or main branch and contains
    a snapshot of codebundles at that point in time.
    """
    __tablename__ = "codecollection_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    codecollection_id = Column(Integer, ForeignKey("codecollections.id"), nullable=False)
    
    # Version information
    version_name = Column(String(100), nullable=False, index=True)  # e.g., "v1.0.0", "main", "develop"
    git_ref = Column(String(100), nullable=False)   # The actual git reference (tag, branch, commit hash)
    display_name = Column(String(200))              # Human-readable version name
    description = Column(Text)                      # Version notes/description
    version_type = Column(String(20), default="tag")  # "tag", "branch", "main"
    
    # Version metadata
    is_latest = Column(Boolean, default=False)      # Mark the latest version
    is_prerelease = Column(Boolean, default=False)  # Mark pre-releases (alpha, beta, rc)
    version_date = Column(DateTime)                 # When the version was created/last updated
    
    # Sync metadata
    synced_at = Column(DateTime)                    # When this version was last synced
    is_active = Column(Boolean, default=True)      # Whether this version is available
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    codecollection = relationship("CodeCollection", back_populates="versions")
    codebundles = relationship("VersionCodebundle", back_populates="version", cascade="all, delete-orphan")
    raw_files = relationship("RawRepositoryData", back_populates="version", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CodeCollectionVersion(id={self.id}, collection='{self.codecollection.name if self.codecollection else 'Unknown'}', version='{self.version_name}')>"


class VersionCodebundle(Base):
    """
    Represents a codebundle within a specific CodeCollection version.
    This allows us to track which codebundles existed in each version
    and their state at that point in time.
    """
    __tablename__ = "version_codebundles"
    
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("codecollection_versions.id"), nullable=False)
    
    # Codebundle snapshot data (copied from the main codebundle at version time)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255))
    description = Column(Text)
    doc = Column(Text)
    
    # Robot file metadata
    author = Column(String(255))
    support_tags = Column(JSON, default=list)
    categories = Column(JSON, default=list)
    
    # File paths and URLs (relative to this version)
    runbook_path = Column(String(500))
    sli_path = Column(String(500))
    meta_path = Column(String(500))
    runbook_source_url = Column(String(500))
    
    # Task and SLI data (snapshot)
    tasks = Column(JSON, default=list)
    slis = Column(JSON, default=list)
    task_count = Column(Integer, default=0)
    sli_count = Column(Integer, default=0)
    
    # Version-specific metadata
    added_in_version = Column(Boolean, default=False)    # New in this version
    modified_in_version = Column(Boolean, default=False) # Modified in this version
    removed_in_version = Column(Boolean, default=False)  # Removed in this version
    
    # Discovery info (snapshot)
    discovery_info = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    version = relationship("CodeCollectionVersion", back_populates="codebundles")
    
    def __repr__(self):
        return f"<VersionCodebundle(id={self.id}, version='{self.version.version_name if self.version else 'Unknown'}', name='{self.name}')>"

