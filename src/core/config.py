from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    QDRANT_HOST: str
    QDRANT_PORT: int
    QDRANT_COLLECTION_NAME: str
    
    VECTOR_DIMENSION: int
    EMBEDDING_MODEL: str
    OLLAMA_BASE_URL: str

    # Celery
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672//"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Upload
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Chunking settings
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    TOKENIZER_MODEL: str = "BAAI/bge-m3"
    CHUNK_CONTEXT_RESERVED_TOKENS: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()