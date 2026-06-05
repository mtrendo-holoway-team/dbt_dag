from dbt_dag.metadata.models import RuntimeDataSource
from dbt_dag.partitions.models import (
    ModelPartitionCalendarDTO,
    PartitionMonthDTO,
    PartitionSyncStatus,
)


def block_id(block_name: str, selection_token: str) -> str:
    return f"inspector-block-{block_name}-{selection_token}"


def source_label(source: RuntimeDataSource) -> str:
    if source == RuntimeDataSource.WAREHOUSE:
        return "warehouse"
    if source == RuntimeDataSource.RUN_RESULTS:
        return "run_results"
    return "none"


def partition_status_label(calendar: ModelPartitionCalendarDTO) -> str:
    if calendar.sync_status == PartitionSyncStatus.RUNNING:
        return "Обновляется"
    if calendar.sync_status == PartitionSyncStatus.FAILED:
        return "Ошибка обновления"
    if calendar.is_stale:
        return "Устаревшие данные"
    return "Обновлено"


def partition_status_class(calendar: ModelPartitionCalendarDTO) -> str:
    if calendar.sync_status == PartitionSyncStatus.FAILED:
        return "text-rose-400"
    if calendar.sync_status == PartitionSyncStatus.RUNNING:
        return "text-cyan-400"
    return "text-emerald-400"


def group_months_by_year(months: list[PartitionMonthDTO]) -> list[list[PartitionMonthDTO]]:
    groups: list[list[PartitionMonthDTO]] = []
    current_group: list[PartitionMonthDTO] = []
    current_year: int | None = None
    for month in months:
        if current_year != month.year:
            if current_group:
                groups.append(current_group)
            current_group = [month]
            current_year = month.year
            continue
        current_group.append(month)
    if current_group:
        groups.append(current_group)
    return groups
