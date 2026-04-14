from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DailyFeatureRow(Base):
    __tablename__ = "daily_features"
    __table_args__ = (
        UniqueConstraint(
            "location_id", "source", "date", "feature_config_hash",
            name="uq_daily_features_loc_src_date_hash",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("locations.id"))
    source: Mapped[str] = mapped_column(String(63))
    date: Mapped[date] = mapped_column(Date)
    features_json: Mapped[dict] = mapped_column(JSONB)
    feature_config_hash: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
