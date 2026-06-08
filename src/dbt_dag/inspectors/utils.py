from dbt_dag.metadata.models import RuntimeDataSource
from dbt_dag.partitions.models import ModelPartitionCalendarDTO
from dbt_dag.partitions.models import PartitionMonthDTO
from dbt_dag.partitions.models import PartitionSyncStatus
from dbt_dag.tests.models import ModelTestStatus


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


def test_status_dot_class(status: ModelTestStatus) -> str:
    if status == ModelTestStatus.PASSED:
        return "status-dot status-dot-passed"
    if status == ModelTestStatus.STALE:
        return "status-dot status-dot-stale"
    if status == ModelTestStatus.FAILED:
        return "status-dot status-dot-failed"
    return "status-dot status-dot-missing"


def test_status_label(status: ModelTestStatus) -> str:
    if status == ModelTestStatus.PASSED:
        return "Пройден"
    if status == ModelTestStatus.STALE:
        return "Не запускался больше суток"
    if status == ModelTestStatus.FAILED:
        return "Ошибка"
    return "Нет тестов"
