"""Add model_run_time, forecast_hour, model_name to weather_records

Revision ID: 005
Revises: 004
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "weather_records",
        sa.Column("model_run_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "weather_records",
        sa.Column("forecast_hour", sa.Integer(), nullable=True),
    )
    op.add_column(
        "weather_records",
        sa.Column("model_name", sa.String(63), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("weather_records", "model_name")
    op.drop_column("weather_records", "forecast_hour")
    op.drop_column("weather_records", "model_run_time")
