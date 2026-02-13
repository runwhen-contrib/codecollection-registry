from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class RawYamlData(Base):
    """Store raw YAML data from codecollections.yaml"""
    __tablename__ = "raw_yaml_data"
    
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(255), nullable=False, index=True)  # e.g., "codecollections.yaml"
    content = Column(Text, nullable=False)  # Raw YAML content
    parsed_data = Column(Text)  # JSON representation of parsed YAML
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class RawRepositoryData(Base):
    """Store raw repository data from cloned repos"""
    __tablename__ = "raw_repository_data"
    
    id = Column(Integer, primary_key=True, index=True)
    collection_slug = Column(String(255), nullable=False, index=True)
    repository_path = Column(String(500), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_content = Column(Text, nullable=False)
    file_type = Column(String(50), nullable=False)  # e.g., "robot", "yaml", "json"
    version_id = Column(Integer, ForeignKey("codecollection_versions.id"), nullable=True, index=True)
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    version = relationship("CodeCollectionVersion", back_populates="raw_files")

