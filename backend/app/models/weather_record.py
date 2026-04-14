from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WeatherRecord(Base):
    __tablename__ = "weather_records"
    __table_args__ = (
        UniqueConstraint("location_id", "source", "valid_time_utc"),
        Index("ix_weather_records_location_valid_time", "location_id", "valid_time_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id"))
    source: Mapped[str] = mapped_column(String(63))
    valid_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_time_local: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    true_wind_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    true_wind_direction: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    cloud_cover: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
