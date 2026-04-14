from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SourceBiasCorrection(Base):
    __tablename__ = "source_bias_corrections"
    __table_args__ = (
        UniqueConstraint(
            "location_id", "forecast_source", "historical_source", "feature_name",
            name="uq_bias_corrections_loc_sources_feature",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id"))
    forecast_source: Mapped[str] = mapped_column(String(63))
    historical_source: Mapped[str] = mapped_column(String(63))
    feature_name: Mapped[str] = mapped_column(String(63))
    bias_mean: Mapped[float] = mapped_column(Float)
    bias_std: Mapped[float] = mapped_column(Float)
    calibration_start: Mapped[date] = mapped_column(Date)
    calibration_end: Mapped[date] = mapped_column(Date)
    sample_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
