"""Add daily_features, library_build_jobs, source_bias_corrections tables

Revision ID: 006
Revises: 005
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_features",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("source", sa.String(63), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("features_json", JSONB, nullable=False),
        sa.Column("feature_config_hash", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "location_id", "source", "date", "feature_config_hash",
            name="uq_daily_features_loc_src_date_hash",
        ),
    )

    op.create_table(
        "library_build_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("source", sa.String(63), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(31), nullable=False, server_default="'pending'"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_table(
        "source_bias_corrections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("forecast_source", sa.String(63), nullable=False),
        sa.Column("historical_source", sa.String(63), nullable=False),
        sa.Column("feature_name", sa.String(63), nullable=False),
        sa.Column("bias_mean", sa.Float(), nullable=False),
        sa.Column("bias_std", sa.Float(), nullable=False),
        sa.Column("calibration_start", sa.Date(), nullable=False),
        sa.Column("calibration_end", sa.Date(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "location_id", "forecast_source", "historical_source", "feature_name",
            name="uq_bias_corrections_loc_sources_feature",
        ),
    )


def downgrade() -> None:
    op.drop_table("source_bias_corrections")
    op.drop_table("library_build_jobs")
    op.drop_table("daily_features")
