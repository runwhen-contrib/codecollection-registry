from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@database:5432/codecollection_registry"
    
    # GitHub Integration
    GITHUB_TOKEN: str = "your_github_token_here"
    GITHUB_WEBHOOK_SECRET: str = "your_webhook_secret_here"
    GITHUB_OWNER: str = "runwhen-contrib"
    GITHUB_REPO: str = "codecollection-registry"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # AI Integration
    OPENAI_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4"
    AI_ENHANCEMENT_ENABLED: bool = False
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT_NAME: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    
    # AI Service Provider (openai, azure-openai)
    AI_SERVICE_PROVIDER: str = "openai"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "CodeCollection Registry"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
