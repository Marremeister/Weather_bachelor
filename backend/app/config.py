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

    # GFS forecast settings
    grib_cache_dir: str = "../data/grib_cache"
    gfs_cycle: str = "00"
    gfs_forecast_hours: str = "015,018"
    analog_match_local_hour: int = 9
    point_buffer_deg: float = 0.40
    gfs_download_timeout: int = 180
    gfs_fallback_to_open_meteo: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def gfs_forecast_hours_list(self) -> list[str]:
        """Parse comma-separated forecast hours into a list."""
        return [h.strip() for h in self.gfs_forecast_hours.split(",") if h.strip()]

    @field_validator("database_url")
    @classmethod
    def fix_railway_dsn(cls, v: str) -> str:
        """Railway provides postgresql:// but psycopg needs postgresql+psycopg://."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v


settings = Settings()
