import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    load_dotenv(override=False)

class Settings(BaseSettings):
    PROJECT_NAME: str = "Overmend AI — Autonomous Recovery PaaS API"
    ENVIRONMENT: str = "development"
    
    # PostgreSQL Settings
    DATABASE_URL: str = "sqlite+aiosqlite:///./test_recovery.db"
    SYNC_DATABASE_URL: str = "sqlite:///./test_recovery.db"
    
    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery Settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Retrieval Settings
    SHARED_KNOWLEDGE_MODE: bool = False

    # Authentication Settings
    AUTH_PROVIDER: str = "header"  # "header" or "jwt"
    JWT_SECRET: str = "production-secret-key-change-in-env-32bytes-minimum"
    JWT_ALGORITHM: str = "HS256"
    
    # CORS & Security
    ALLOWED_ORIGINS: str = "*"  # Comma-separated list of origins, e.g. "https://app.example.com,http://localhost:5173"
    STRICT_SANDBOX: bool = False
    ENFORCE_WEBHOOK_SECRET: bool = False

    # GitHub App Settings
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_PRIVATE_KEY: Optional[str] = None
    GITHUB_INSTALLATION_ID: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: Optional[str] = None
    GITHUB_TRUST_THRESHOLD: float = 0.90

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH) if ENV_PATH.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )

settings = Settings()

# Resolve relative GITHUB_PRIVATE_KEY path to absolute
if settings.GITHUB_PRIVATE_KEY and not os.path.isabs(settings.GITHUB_PRIVATE_KEY) and "BEGIN" not in settings.GITHUB_PRIVATE_KEY:
    resolved_key_path = ROOT_DIR / settings.GITHUB_PRIVATE_KEY.lstrip("./\\")
    if resolved_key_path.exists():
        settings.GITHUB_PRIVATE_KEY = str(resolved_key_path)
        os.environ["GITHUB_PRIVATE_KEY"] = str(resolved_key_path)

# Ensure postgresql connection string uses async driver
if settings.DATABASE_URL.startswith("postgresql://"):
    settings.DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Use SQLite for local development/testing when PostgreSQL is not explicitly configured or available
if settings.ENVIRONMENT == "development":
    settings.DATABASE_URL = "sqlite+aiosqlite:///./test_recovery.db"
    settings.SYNC_DATABASE_URL = "sqlite:///./test_recovery.db"



