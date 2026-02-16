from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "securenotes"
    app_version: str = "0.1.0"
    database_url: str

    # Day 2: jwt token for bearer authentication
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15

    # Day 2: Rate limiting
    redis_url: str

    # Ollama LLM for generative RAG
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout: int = 120

settings = Settings()
