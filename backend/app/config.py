from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/seabreeze"
    app_env: str = "development"
    weather_cache_dir: str = "../data/cache"
    default_latitude: float = 33.708965
    default_longitude: float = -118.268343
    default_timezone: str = "America/Los_Angeles"
    allowed_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("database_url")
    @classmethod
    def fix_railway_dsn(cls, v: str) -> str:
        """Railway provides postgresql:// but psycopg needs postgresql+psycopg://."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v


settings = Settings()
