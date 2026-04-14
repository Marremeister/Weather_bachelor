from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalogResult(Base):
    __tablename__ = "analog_results"
    __table_args__ = (
        Index("ix_analog_results_run_rank", "analysis_run_id", "rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analysis_runs.id")
    )
    analog_date: Mapped[date] = mapped_column(Date)
    rank: Mapped[int] = mapped_column(Integer)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
