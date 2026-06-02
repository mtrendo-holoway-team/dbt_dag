"""Create initial task and manifest state tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "node_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("node_id", sa.String(length=512), nullable=False, index=True),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("logs_excerpt", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "manifest_source_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manifest_path", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("manifest_source_state")
    op.drop_table("node_tasks")
