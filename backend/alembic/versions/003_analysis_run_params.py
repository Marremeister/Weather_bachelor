"""Add historical date range and top_n to analysis_runs

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column("historical_start_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("historical_end_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("top_n", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_runs", "top_n")
    op.drop_column("analysis_runs", "historical_end_date")
    op.drop_column("analysis_runs", "historical_start_date")
