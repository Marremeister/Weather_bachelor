"""Add weather_stations and observations tables

Revision ID: 008
Revises: 007
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weather_stations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("station_code", sa.String(31), nullable=False, unique=True),
        sa.Column("source", sa.String(63), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("timezone", sa.String(63), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("weather_stations.id"),
            nullable=False,
        ),
        sa.Column("observation_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_time_local", sa.DateTime(timezone=False), nullable=False),
        sa.Column("wind_speed", sa.Float(), nullable=True),
        sa.Column("wind_direction", sa.Float(), nullable=True),
        sa.Column("gust_speed", sa.Float(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("pressure", sa.Float(), nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "station_id", "observation_time_utc",
            name="uq_observations_station_time",
        ),
        sa.Index(
            "ix_observations_station_time",
            "station_id", "observation_time_utc",
        ),
    )


def downgrade() -> None:
    op.drop_table("observations")
    op.drop_table("weather_stations")
