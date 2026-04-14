from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_runs_location_target_date", "location_id", "target_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id"))
    target_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(31))
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    historical_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    historical_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    top_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str | None] = mapped_column(String(31), nullable=True)
    forecast_source: Mapped[str | None] = mapped_column(String(63), nullable=True)
    historical_source: Mapped[str | None] = mapped_column(String(63), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
