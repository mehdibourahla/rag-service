"""Configuration management using pydantic-settings."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service configuration
    app_name: str = Field(default="rag-service", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # API configuration
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8001, alias="API_PORT")

    # Storage paths
    upload_dir: Path = Field(default=Path("./data/uploads"), alias="UPLOAD_DIR")
    processed_dir: Path = Field(default=Path("./data/processed"), alias="PROCESSED_DIR")
    chunks_dir: Path = Field(default=Path("./data/chunks"), alias="CHUNKS_DIR")

    # Qdrant configuration
    qdrant_host: str = Field(default="localhost", alias="QDRANT_HOST")
    qdrant_port: int = Field(default=6333, alias="QDRANT_PORT")
    qdrant_collection: str = Field(default="documents", alias="QDRANT_COLLECTION")

    # Redis configuration
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_db: int = Field(default=0, alias="REDIS_DB")

    # OpenAI API
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_dir.mkdir(parents=True, exist_ok=True)

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def qdrant_url(self) -> str:
        """Get Qdrant connection URL."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"


# Global settings instance
settings = Settings()
