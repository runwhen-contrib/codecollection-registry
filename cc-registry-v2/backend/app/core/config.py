from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import field_validator, model_validator


class Settings(BaseSettings):
    # Database - can be configured via URL or individual components
    DATABASE_URL: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[int] = 5432
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_NAME: Optional[str] = None
    
    # GitHub Integration
    GITHUB_TOKEN: str = "your_github_token_here"
    GITHUB_WEBHOOK_SECRET: str = "your_webhook_secret_here"
    GITHUB_OWNER: str = "runwhen-contrib"
    GITHUB_REPO: str = "codecollection-registry"

    # GitHub App Authentication (preferred over GITHUB_TOKEN when configured)
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_PRIVATE_KEY: Optional[str] = None
    GITHUB_APP_INSTALLATION_ID: Optional[int] = None

    # Target repo for intake wizard issue creation
    GITHUB_INTAKE_REPO: str = "runwhen-contrib/codecollection-registry"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Redis - can be configured via URL or Sentinel
    REDIS_URL: Optional[str] = None
    REDIS_SENTINEL_HOSTS: Optional[str] = None  # Comma-separated: "host1:26379,host2:26379,host3:26379"
    REDIS_SENTINEL_MASTER: Optional[str] = "mymaster"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    # AI Integration
    OPENAI_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4"
    AI_ENHANCEMENT_ENABLED: bool = False
    
    # Azure OpenAI Configuration (GPT / chat completions)
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT_NAME: Optional[str] = None
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    
    # Azure OpenAI Embedding Configuration (separate endpoint supported)
    AZURE_OPENAI_EMBEDDING_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_EMBEDDING_API_KEY: Optional[str] = None
    AZURE_OPENAI_EMBEDDING_API_VERSION: Optional[str] = None
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-3-small"
    EMBEDDING_BATCH_SIZE: int = 100
    
    # AI Service Provider (openai, azure-openai)
    AI_SERVICE_PROVIDER: str = "openai"
    
    # MCP Server
    MCP_SERVER_URL: str = "http://mcp-http:8000"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "CodeCollection Registry"

    # Config-file paths (codecollections.yaml, schedules.yaml, sources.yaml).
    #
    # Historically these were hardcoded to /app/<file>.yaml and mounted from
    # ConfigMaps using `subPath`, which has a critical limitation: subPath
    # mounts do NOT receive ConfigMap updates from the kubelet, so any
    # change to the ConfigMap requires a pod restart to take effect. This
    # is the bug that made the stewartshea typo "stick" in registry-test
    # even after the ConfigMap was fixed.
    #
    # By exposing these as env-driven settings, k8s deployments can mount
    # each ConfigMap as a *directory* (no subPath) and point the env vars
    # at the resulting paths (e.g. /etc/cc-registry/codecollections/codecollections.yaml).
    # Directory mounts auto-update; subPath mounts don't.
    #
    # Defaults preserve the legacy /app/<file>.yaml behavior so local dev
    # (docker-compose bind-mounts) and existing deployments continue to
    # work unchanged.
    #
    # CAVEAT: `schedules.yaml` is only loaded at Celery beat startup
    # (see app/tasks/celery_app.py::load_schedules_from_yaml). Hot-reload
    # via directory mount avoids the *deploy* step but you still need to
    # restart the scheduler pod for new schedules to take effect.
    # `codecollections.yaml` and `sources.yaml` are re-read on every task
    # invocation and pick up changes within ~60s of a ConfigMap edit.
    CODECOLLECTIONS_FILE: str = "/app/codecollections.yaml"
    SCHEDULES_FILE: str = "/app/schedules.yaml"
    SOURCES_FILE: str = "/app/sources.yaml"

    @model_validator(mode='after')
    def construct_urls(self):
        """Construct DATABASE_URL and REDIS_URL from components if not provided"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Build DATABASE_URL from components if not provided
        if not self.DATABASE_URL:
            if all([self.DB_HOST, self.DB_USER, self.DB_PASSWORD, self.DB_NAME]):
                self.DATABASE_URL = f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            else:
                # Fallback to default for development
                self.DATABASE_URL = "postgresql://user:password@database:5432/codecollection_registry"
        
        # Build REDIS_URL. Sentinel ALWAYS wins when REDIS_SENTINEL_HOSTS
        # is set, even if a REDIS_URL was also provided via env. Helm
        # charts commonly set both, and pointing a Redis client at a
        # Sentinel data-plane port (26379) results in "Only HELLO
        # messages are accepted" errors on every command. See
        # tasks/celery_app.py::_configure_broker_url for the matching
        # Celery-side precedence rule.
        if self.REDIS_SENTINEL_HOSTS:
            if self.REDIS_URL:
                logger.info(
                    "Both REDIS_SENTINEL_HOSTS and REDIS_URL are set; "
                    "preferring Sentinel. Remove REDIS_URL from the deployment "
                    "to silence this notice."
                )
            # Format: sentinel://[:password@]host1:port1,host2:port2/service_name/db_number
            auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
            self.REDIS_URL = (
                f"sentinel://{auth}{self.REDIS_SENTINEL_HOSTS}/"
                f"{self.REDIS_SENTINEL_MASTER}/{self.REDIS_DB}"
            )
            logger.info(
                f"Constructed Sentinel URL. REDIS_DB remains: {self.REDIS_DB} "
                f"(type: {type(self.REDIS_DB)})"
            )
        elif not self.REDIS_URL:
            self.REDIS_URL = "redis://redis:6379/0"
        
        # Validate REDIS_DB is correct type
        if self.REDIS_SENTINEL_HOSTS:
            # Ensure REDIS_DB is an integer when using Sentinel
            if isinstance(self.REDIS_DB, str):
                logger.warning(f"REDIS_DB is string '{self.REDIS_DB}', converting to int")
                try:
                    self.REDIS_DB = int(self.REDIS_DB)
                except ValueError as e:
                    logger.error(f"Failed to convert REDIS_DB '{self.REDIS_DB}' to int: {e}, defaulting to 0")
                    self.REDIS_DB = 0
        
        return self
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
