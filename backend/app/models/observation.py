from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("station_id", "observation_time_utc"),
        Index("ix_observations_station_time", "station_id", "observation_time_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(Integer, ForeignKey("weather_stations.id"))
    observation_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observation_time_local: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    wind_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_direction: Mapped[float | None] = mapped_column(Float, nullable=True)
    gust_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
