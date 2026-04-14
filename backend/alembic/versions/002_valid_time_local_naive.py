"""Make valid_time_local a naive timestamp

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Convert timestamptz → timestamp (strips timezone, keeps the stored instant).
    # Existing rows were inserted with the local tz offset so the instant *is*
    # the correct wall-clock time once we drop the tz qualifier.  Any rows that
    # were normalised to UTC by Postgres need to be re-fetched (drop & re-cache).
    op.execute(
        "ALTER TABLE weather_records "
        "ALTER COLUMN valid_time_local TYPE timestamp WITHOUT TIME ZONE "
        "USING valid_time_local AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE weather_records "
        "ALTER COLUMN valid_time_local TYPE timestamp WITH TIME ZONE "
        "USING valid_time_local AT TIME ZONE 'UTC'"
    )
