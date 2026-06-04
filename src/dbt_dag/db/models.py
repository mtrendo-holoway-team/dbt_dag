from datetime import date
from datetime import datetime

from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class Base(DeclarativeBase):
    pass


class NodeTaskRecord(Base):
    __tablename__ = "node_tasks"

    record_id: Mapped[int] = mapped_column("id", Integer, primary_key=True)
    node_id: Mapped[str] = mapped_column(String(512), index=True)
    command: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    logs_excerpt: Mapped[str] = mapped_column(Text, default="")


class ManifestSourceStateRecord(Base):
    __tablename__ = "manifest_source_state"

    record_id: Mapped[int] = mapped_column("id", Integer, primary_key=True)
    manifest_path: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(128))
    last_ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ModelPartitionSnapshotRecord(Base):
    __tablename__ = "model_partition_snapshots"

    record_id: Mapped[int] = mapped_column("id", Integer, primary_key=True)
    model_unique_id: Mapped[str] = mapped_column(String(512), index=True)
    partition_date: Mapped[date] = mapped_column(Date, index=True)
    partition_key: Mapped[str] = mapped_column(String(255))
    row_count: Mapped[int] = mapped_column(Integer)
    source_inserted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ModelPartitionSyncStateRecord(Base):
    __tablename__ = "model_partition_sync_state"

    record_id: Mapped[int] = mapped_column("id", Integer, primary_key=True)
    model_unique_id: Mapped[str] = mapped_column(String(512), index=True, unique=True)
    last_source_inserted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(32))
    last_error: Mapped[str] = mapped_column(Text, default="")
