from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: str = "production"
    log_level: str = "INFO"
    domain: str = "localhost"

    # Security
    secret_key: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    ip_hash_salt: str

    # Database
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "mentorix"
    postgres_user: str
    postgres_password: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # OpenAI (required for embeddings; optional if all tenants use Ollama LLM)
    openai_api_key: str = ""

    # Ollama (local LLM, runs in Docker on mentorix_internal network)
    ollama_url: str = "http://ollama:11434"

    # Upload
    upload_max_size_mb: int = 25
    upload_dir: str = "/uploads"

    # CORS
    admin_cors_origins: str = "https://localhost"

    @property
    def admin_cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.admin_cors_origins.split(",")]

    # Vector DB
    vector_db_backend: str = "pgvector"  # or "qdrant"
    qdrant_url: str = "http://qdrant:6333"

    # Auth security
    max_failed_login_attempts: int = 5
    lockout_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
