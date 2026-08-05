from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    QDRANT_HOST: str
    QDRANT_PORT: int
    QDRANT_COLLECTION_NAME: str
    
    COHERE_API_KEY: str
    LLM_MODEL: str
    LLM_MAX_TOKENS: int
    
    VECTOR_DIMENSION: int
    EMBEDDING_MODEL: str
    RERANK_MODEL: str

    RABBITMQ_URL: str
    REDIS_URL: str 

    LANGFUSE_PUBLIC_KEY: str
    LANGFUSE_SECRET_KEY: str
    LANGFUSE_HOST: str 

    UPLOAD_DIR: str 
    MAX_FILE_SIZE_MB: int 

    CHUNK_SIZE: int 
    CHUNK_OVERLAP: int 
    TOKENIZER_MODEL: str 
    CHUNK_CONTEXT_RESERVED_TOKENS: int

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()