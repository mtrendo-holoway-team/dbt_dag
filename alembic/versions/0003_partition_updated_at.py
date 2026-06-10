"""Add per-partition _dbt_updated_at cache timestamp."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0003_partition_updated_at"
down_revision = "0002_partitions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_partition_snapshots",
        sa.Column("partition_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("model_partition_snapshots", "partition_updated_at")
