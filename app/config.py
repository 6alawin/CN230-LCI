from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    gemini_api_key: str = ''
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_generation_model: str = 'gemini-3.5-flash-lite'
    embedding_dimensions: int = 768
    search_backend: str = 'gemini'
    cloud_snapshot_schema: str = 'lci_verified_20261115'
    local_embedding_model: str = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    local_model_path: str = 'models/lci-embedding'

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
