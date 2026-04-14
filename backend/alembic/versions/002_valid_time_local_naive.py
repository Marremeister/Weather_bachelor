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
    # Existing rows have valid_time_local normalised to UTC by Postgres
    # (timestamptz stores instants, not wall-clock times).  Truncate so
    # re-fetches populate correct naive local times.  Filesystem cache
    # still has the raw API responses, so the next fetch is a tier-2 hit.
    op.execute("TRUNCATE TABLE weather_records")
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
