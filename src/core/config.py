from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    QDRANT_HOST:str
    QDRANT_PORT:int
    QDRANT_COLLECTION_NAME:str
    QDRANT_API_KEY:str

    VECTOR_DIMENSION:int
    EMBEDDING_MODEL:str
    OLLAMA_BASE_URL:str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()