import os


class Settings:
    app_name: str = "EDOS API"
    service_name: str = "edos-api"
    environment: str = os.getenv("ENVIRONMENT", "development")
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))

    # Ollama Local LLM Configuration (Day 26)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    ollama_timeout_seconds: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120.0"))


def get_settings() -> Settings:
    return Settings()
