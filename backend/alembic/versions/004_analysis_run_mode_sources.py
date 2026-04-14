"""Add mode, forecast_source, historical_source to analysis_runs

Revision ID: 004
Revises: 003
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column("mode", sa.String(31), nullable=True),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("forecast_source", sa.String(63), nullable=True),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("historical_source", sa.String(63), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_runs", "historical_source")
    op.drop_column("analysis_runs", "forecast_source")
    op.drop_column("analysis_runs", "mode")
