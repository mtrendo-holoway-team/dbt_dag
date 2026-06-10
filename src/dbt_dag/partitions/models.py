from dataclasses import dataclass
from datetime import date
from datetime import datetime
from enum import StrEnum


class PartitionFillLevel(StrEnum):
    EMPTY = "empty"
    HALF = "half"
    FULL = "full"


class PartitionSyncStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class PartitionSnapshotRow:
    partition_key: str
    partition_date: date
    row_count: int
    source_inserted_at: datetime | None
    partition_updated_at: datetime | None = None


@dataclass(frozen=True)
class ModelPartitionSnapshot:
    model_unique_id: str
    partition_key: str
    partition_date: date
    row_count: int
    source_inserted_at: datetime | None
    synced_at: datetime
    partition_updated_at: datetime | None = None


@dataclass(frozen=True)
class ModelPartitionSyncState:
    model_unique_id: str
    last_source_inserted_at: datetime | None
    last_synced_at: datetime | None
    last_checked_at: datetime | None
    sync_status: PartitionSyncStatus
    last_error: str


@dataclass(frozen=True)
class PartitionDayCellDTO:
    date: date
    row_count: int | None
    fill_level: PartitionFillLevel
    partition_updated_at: datetime | None = None


@dataclass(frozen=True)
class PartitionMonthDTO:
    year: int
    month_label: str
    leading_empty_days: int
    days: list[PartitionDayCellDTO]


@dataclass(frozen=True)
class ModelPartitionCalendarDTO:
    model_unique_id: str
    range_start: date | None
    range_end: date
    median_row_count: float | None
    months: list[PartitionMonthDTO]
    is_stale: bool
    is_refreshing: bool
    last_synced_at: datetime | None
    sync_status: PartitionSyncStatus
    last_error: str
