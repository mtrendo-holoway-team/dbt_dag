from collections import defaultdict
from datetime import date
from datetime import datetime
from statistics import median

from dbt_dag.partitions.models import ModelPartitionCalendarDTO
from dbt_dag.partitions.models import ModelPartitionSnapshot
from dbt_dag.partitions.models import PartitionDayCellDTO
from dbt_dag.partitions.models import PartitionFillLevel
from dbt_dag.partitions.models import PartitionMonthDTO
from dbt_dag.partitions.models import PartitionSyncStatus
from dbt_dag.partitions.repository import ModelPartitionRepository
from dbt_dag.partitions.warehouse import BigQueryPartitionWarehouseReader
from dbt_dag.shared.time import now_msk

_MONTH_LABELS = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь",
}


class ModelPartitionService:
    def __init__(
        self,
        repository: ModelPartitionRepository,
        warehouse_reader: BigQueryPartitionWarehouseReader,
    ) -> None:
        self._repository = repository
        self._warehouse_reader = warehouse_reader

    def supports_partitions(self) -> bool:
        return self._warehouse_reader.supports_partitions()

    def build_calendar(
        self,
        model_unique_id: str,
        runtime_last_updated_at: datetime | None,
    ) -> ModelPartitionCalendarDTO:
        snapshot = self._repository.list_snapshot(model_unique_id)
        sync_state = self._repository.get_sync_state(model_unique_id)
        latest_model_run_at = self._warehouse_reader.fetch_latest_model_run_at(model_unique_id)
        remote_model_updated_at = _latest_datetime(runtime_last_updated_at, latest_model_run_at)
        local_source_inserted_at = (
            sync_state.last_source_inserted_at if sync_state is not None else None
        )
        is_stale = local_source_inserted_at is None or (
            remote_model_updated_at is not None
            and local_source_inserted_at < remote_model_updated_at
        )
        row_count_by_date = _row_count_by_date(snapshot)
        partition_updated_at_by_date = _partition_updated_at_by_date(snapshot)
        median_row_count = _median_row_count(row_count_by_date)
        months = _build_months(
            row_count_by_date,
            partition_updated_at_by_date,
            median_row_count,
        )
        range_start = min(row_count_by_date) if row_count_by_date else None
        sync_status = sync_state.sync_status if sync_state is not None else PartitionSyncStatus.IDLE
        last_error = sync_state.last_error if sync_state is not None else ""
        last_synced_at = sync_state.last_synced_at if sync_state is not None else None
        return ModelPartitionCalendarDTO(
            model_unique_id=model_unique_id,
            range_start=range_start,
            range_end=now_msk().date(),
            median_row_count=median_row_count,
            months=months,
            is_stale=is_stale,
            is_refreshing=sync_status == PartitionSyncStatus.RUNNING,
            last_synced_at=last_synced_at,
            sync_status=sync_status,
            last_error=last_error,
        )


def _row_count_by_date(snapshot: list[ModelPartitionSnapshot]) -> dict[date, int]:
    result: dict[date, int] = defaultdict(int)
    for item in snapshot:
        result[item.partition_date] += item.row_count
    return dict(sorted(result.items()))


def _median_row_count(row_count_by_date: dict[date, int]) -> float | None:
    if not row_count_by_date:
        return None
    return float(median(row_count_by_date.values()))


def _partition_updated_at_by_date(
    snapshot: list[ModelPartitionSnapshot],
) -> dict[date, datetime | None]:
    result: dict[date, datetime | None] = {}
    for item in snapshot:
        if item.partition_updated_at is None:
            continue
        current = result.get(item.partition_date)
        if current is None or item.partition_updated_at < current:
            result[item.partition_date] = item.partition_updated_at
    return result


def _build_months(
    row_count_by_date: dict[date, int],
    partition_updated_at_by_date: dict[date, datetime | None],
    median_row_count: float | None,
) -> list[PartitionMonthDTO]:
    if not row_count_by_date:
        return []
    start_date = min(row_count_by_date)
    end_date = now_msk().date()
    months: list[PartitionMonthDTO] = []
    current_year = start_date.year
    current_month = start_date.month
    while (current_year, current_month) <= (end_date.year, end_date.month):
        month_start = date(current_year, current_month, 1)
        month_end = _month_end(month_start)
        visible_end = min(month_end, end_date)
        leading_empty_days = month_start.weekday()
        days = [
            PartitionDayCellDTO(
                date=current_date,
                row_count=row_count_by_date.get(current_date),
                fill_level=_fill_level(row_count_by_date.get(current_date), median_row_count),
                partition_updated_at=partition_updated_at_by_date.get(current_date),
            )
            for current_date in _date_range(month_start, visible_end)
        ]
        months.append(
            PartitionMonthDTO(
                year=current_year,
                month_label=_MONTH_LABELS[current_month],
                leading_empty_days=leading_empty_days,
                days=days,
            )
        )
        if current_month == 12:
            current_year += 1
            current_month = 1
        else:
            current_month += 1
    months.reverse()
    return months


def _fill_level(row_count: int | None, median_row_count: float | None) -> PartitionFillLevel:
    if row_count is None or median_row_count is None:
        return PartitionFillLevel.EMPTY
    if row_count < median_row_count:
        return PartitionFillLevel.HALF
    return PartitionFillLevel.FULL


def _date_range(start_date: date, end_date: date) -> list[date]:
    days = (end_date - start_date).days
    return [start_date.fromordinal(start_date.toordinal() + offset) for offset in range(days + 1)]


def _month_end(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year, 12, 31)
    next_month = date(month_start.year, month_start.month + 1, 1)
    return date.fromordinal(next_month.toordinal() - 1)


def _latest_datetime(*values: datetime | None) -> datetime | None:
    timestamps = [value for value in values if value is not None]
    return max(timestamps) if timestamps else None
