"""Add model partition snapshot cache tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0002_partitions"
down_revision = "0001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_partition_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_unique_id", sa.String(length=512), nullable=False, index=True),
        sa.Column("partition_date", sa.Date(), nullable=False, index=True),
        sa.Column("partition_key", sa.String(length=255), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("source_inserted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "model_partition_sync_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_unique_id", sa.String(length=512), nullable=False, unique=True, index=True),
        sa.Column("last_source_inserted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("model_partition_sync_state")
    op.drop_table("model_partition_snapshots")
