from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class HelmChart(Base):
    """
    Represents a Helm chart (e.g., runwhen-local) that can have multiple versions.
    """
    __tablename__ = "helm_charts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)  # e.g., "runwhen-local"
    repository_url = Column(String(500), nullable=False)  # e.g., "https://runwhen-contrib.github.io/helm-charts"
    description = Column(Text)
    
    # Chart metadata
    home_url = Column(String(500))
    source_urls = Column(JSON, default=list)  # List of source URLs
    maintainers = Column(JSON, default=list)  # List of maintainer objects
    keywords = Column(JSON, default=list)  # List of keywords
    
    # Sync metadata
    last_synced_at = Column(DateTime)
    sync_enabled = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    versions = relationship("HelmChartVersion", back_populates="chart", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<HelmChart(id={self.id}, name='{self.name}')>"


class HelmChartVersion(Base):
    """
    Represents a specific version of a Helm chart with its values schema and defaults.
    """
    __tablename__ = "helm_chart_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    chart_id = Column(Integer, ForeignKey("helm_charts.id"), nullable=False)
    
    # Version information
    version = Column(String(50), nullable=False, index=True)  # e.g., "0.0.21", "1.2.3"
    app_version = Column(String(50))  # Application version (different from chart version)
    description = Column(Text)
    
    # Chart metadata for this version
    created_date = Column(DateTime)  # When this chart version was created
    digest = Column(String(100))  # Chart digest/hash
    
    # Values and schema
    default_values = Column(JSON, default=dict)  # Default values.yaml content
    values_schema = Column(JSON, default=dict)  # values.schema.json content
    
    # Version metadata
    is_latest = Column(Boolean, default=False)
    is_prerelease = Column(Boolean, default=False)
    is_deprecated = Column(Boolean, default=False)
    
    # Sync metadata
    synced_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    chart = relationship("HelmChart", back_populates="versions")
    
    def __repr__(self):
        return f"<HelmChartVersion(id={self.id}, chart='{self.chart.name if self.chart else 'Unknown'}', version='{self.version}')>"


class HelmChartTemplate(Base):
    """
    Stores configuration templates for different use cases of a helm chart version.
    This allows users to start with pre-configured templates.
    """
    __tablename__ = "helm_chart_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    chart_version_id = Column(Integer, ForeignKey("helm_chart_versions.id"), nullable=False)
    
    # Template information
    name = Column(String(100), nullable=False)  # e.g., "Basic Setup", "Production Ready", "Development"
    description = Column(Text)
    category = Column(String(50))  # e.g., "basic", "production", "development", "advanced"
    
    # Template configuration
    template_values = Column(JSON, default=dict)  # Pre-configured values for this template
    required_fields = Column(JSON, default=list)  # Fields that must be customized by user
    
    # Template metadata
    is_default = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    chart_version = relationship("HelmChartVersion")
    
    def __repr__(self):
        return f"<HelmChartTemplate(id={self.id}, name='{self.name}', version='{self.chart_version.version if self.chart_version else 'Unknown'}')>"
