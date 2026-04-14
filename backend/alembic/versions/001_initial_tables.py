"""initial tables

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("timezone", sa.String(63), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "weather_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id"),
            nullable=False,
        ),
        sa.Column("source", sa.String(63), nullable=False),
        sa.Column("valid_time_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_time_local", sa.DateTime(timezone=True), nullable=False),
        sa.Column("true_wind_speed", sa.Float(), nullable=True),
        sa.Column("true_wind_direction", sa.Float(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("pressure", sa.Float(), nullable=True),
        sa.Column("cloud_cover", sa.Float(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "location_id", "source", "valid_time_utc",
            name="uq_weather_records_loc_src_time",
        ),
    )
    op.create_index(
        "ix_weather_records_location_valid_time",
        "weather_records",
        ["location_id", "valid_time_utc"],
    )

    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id"),
            nullable=False,
        ),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(31), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_analysis_runs_location_target_date",
        "analysis_runs",
        ["location_id", "target_date"],
    )

    op.create_table(
        "analog_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_run_id",
            sa.Integer(),
            sa.ForeignKey("analysis_runs.id"),
            nullable=False,
        ),
        sa.Column("analog_date", sa.Date(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("distance", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_analog_results_run_rank",
        "analog_results",
        ["analysis_run_id", "rank"],
    )


def downgrade() -> None:
    op.drop_table("analog_results")
    op.drop_table("analysis_runs")
    op.drop_table("weather_records")
    op.drop_table("locations")
