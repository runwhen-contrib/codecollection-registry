from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/codecollection_registry"
    
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
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # AI Integration (for future use)
    CURSOR_API_KEY: Optional[str] = None
    
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
