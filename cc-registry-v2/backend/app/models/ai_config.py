from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON
from datetime import datetime
from app.core.database import Base


class AIConfiguration(Base):
    __tablename__ = "ai_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # AI Service Configuration
    service_provider = Column(String(50), default="openai")  # openai, azure-openai, anthropic, etc.
    api_key = Column(String(500))  # API key or token
    model_name = Column(String(100), default="gpt-4")
    
    # Azure OpenAI specific settings
    azure_endpoint = Column(String(500))  # Azure OpenAI endpoint URL
    azure_deployment_name = Column(String(100))  # Deployment name in Azure
    api_version = Column(String(20), default="2024-02-15-preview")  # Azure API version
    
    # Enhancement Settings
    enhancement_enabled = Column(Boolean, default=False)
    auto_enhance_new_bundles = Column(Boolean, default=False)
    enhancement_prompt_template = Column(Text)
    
    # Rate Limiting
    max_requests_per_hour = Column(Integer, default=100)
    max_concurrent_requests = Column(Integer, default=5)
    
    # Configuration metadata
    created_by = Column(String(255))  # Admin user who created this config
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AIConfiguration(id={self.id}, provider='{self.service_provider}', active={self.is_active})>"


