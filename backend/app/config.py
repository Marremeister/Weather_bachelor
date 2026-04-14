from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/seabreeze"
    app_env: str = "development"
    weather_cache_dir: str = "../data/cache"
    default_latitude: float = 33.708965
    default_longitude: float = -118.268343
    default_timezone: str = "America/Los_Angeles"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
