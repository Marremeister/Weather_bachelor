"""Add forecast_composite JSONB column to analysis_runs

Revision ID: 007
Revises: 006
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("forecast_composite", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_runs", "forecast_composite")
