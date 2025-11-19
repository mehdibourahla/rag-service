"""Configuration management using pydantic-settings."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service configuration
    app_name: str = Field(default="pingo-chatbot", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # API configuration
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8001, alias="API_PORT")
    allowed_origins: str = Field(default="http://localhost:3000", alias="ALLOWED_ORIGINS")

    # Storage paths
    upload_dir: Path = Field(default=Path("./data/uploads"), alias="UPLOAD_DIR")
    processed_dir: Path = Field(default=Path("./data/processed"), alias="PROCESSED_DIR")
    chunks_dir: Path = Field(default=Path("./data/chunks"), alias="CHUNKS_DIR")

    # Qdrant configuration
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_collection: str = Field(default="documents", alias="QDRANT_COLLECTION")

    # Database configuration
    database_url: str = Field(
        default="postgresql://pingo:pingo@localhost:5432/pingo",
        alias="DATABASE_URL"
    )

    # Redis configuration (for job queue)
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")

    # Authentication
    secret_key: str = Field(default="change-this-secret-key-in-production", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, alias="ACCESS_TOKEN_EXPIRE_MINUTES")  # 7 days

    # OpenAI API
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # Sentry (optional)
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")

    # Model configurations
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")

    # Chunking configuration
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, alias="CHUNK_OVERLAP")

    # Retrieval configuration
    retrieval_top_k: int = Field(default=20, alias="RETRIEVAL_TOP_K")
    rerank_top_k: int = Field(default=10, alias="RERANK_TOP_K")  # Reduce candidates before LLM reranking
    final_top_k: int = Field(default=5, alias="FINAL_TOP_K")

    # Processing configuration
    max_workers: int = Field(default=4, alias="MAX_WORKERS")

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate that SECRET_KEY is secure and changed from default."""
        if v == "change-this-secret-key-in-production":
            raise ValueError(
                "SECRET_KEY must be changed from default value. "
                "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        if len(v) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters long (current: {len(v)}). "
                "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        return v

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        """Validate that OpenAI API key is provided."""
        if not v or v.strip() == "":
            raise ValueError(
                "OPENAI_API_KEY is required. "
                "Get your API key from https://platform.openai.com/api-keys"
            )
        return v

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

    @property
    def qdrant_url(self) -> str:
        """Get Qdrant connection URL."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def get_allowed_origins(self) -> list[str]:
        """Parse ALLOWED_ORIGINS from comma-separated string."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]


# Global settings instance
settings = Settings()
