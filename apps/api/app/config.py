import os


class Settings:
    app_name: str = "EDOS API"
    service_name: str = "edos-api"
    environment: str = os.getenv("ENVIRONMENT", "development")
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))


def get_settings() -> Settings:
    return Settings()
