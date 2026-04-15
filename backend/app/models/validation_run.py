from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id"))
    evaluation_method: Mapped[str] = mapped_column(String(31))  # temporal_split | leave_one_out
    exclusion_buffer_days: Mapped[int] = mapped_column(Integer, server_default="7")
    top_n: Mapped[int] = mapped_column(Integer, server_default="10")

    library_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    library_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    test_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    test_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    historical_source: Mapped[str | None] = mapped_column(String(63), nullable=True)
    forecast_source: Mapped[str | None] = mapped_column(String(63), nullable=True)

    total_days: Mapped[int] = mapped_column(Integer, server_default="0")
    completed_days: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[str] = mapped_column(String(31), server_default="'queued'")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    aggregate_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    gate_sensitivity: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source_stratification: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    per_day_results: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
