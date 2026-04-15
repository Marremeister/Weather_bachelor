"""Add validation_runs table

Revision ID: 009
Revises: 008
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id"),
            nullable=False,
        ),
        sa.Column("evaluation_method", sa.String(31), nullable=False),
        sa.Column("exclusion_buffer_days", sa.Integer(), server_default="7"),
        sa.Column("top_n", sa.Integer(), server_default="10"),
        sa.Column("library_start_date", sa.Date(), nullable=True),
        sa.Column("library_end_date", sa.Date(), nullable=True),
        sa.Column("test_start_date", sa.Date(), nullable=True),
        sa.Column("test_end_date", sa.Date(), nullable=True),
        sa.Column("historical_source", sa.String(63), nullable=True),
        sa.Column("forecast_source", sa.String(63), nullable=True),
        sa.Column("total_days", sa.Integer(), server_default="0"),
        sa.Column("completed_days", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(31), server_default="'queued'"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("aggregate_metrics", JSONB, nullable=True),
        sa.Column("gate_sensitivity", JSONB, nullable=True),
        sa.Column("source_stratification", JSONB, nullable=True),
        sa.Column("per_day_results", JSONB, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("validation_runs")
