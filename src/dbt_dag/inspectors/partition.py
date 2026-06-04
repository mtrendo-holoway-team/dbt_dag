from typing import Any

from dbt_dag.inspectors.dto import NodeInspectorContextDTO
from dbt_dag.inspectors.utils import block_id
from dbt_dag.inspectors.utils import group_months_by_year
from dbt_dag.inspectors.utils import partition_fill_class
from dbt_dag.inspectors.utils import partition_status_class
from dbt_dag.inspectors.utils import partition_status_label
from dbt_dag.partitions.models import ModelPartitionCalendarDTO
from dbt_dag.partitions.models import PartitionDayCellDTO
from dbt_dag.partitions.models import PartitionMonthDTO

TEMPLATE_NAME = "inspectors/blocks/partition.html"


def build_template_context(inspector: NodeInspectorContextDTO) -> dict[str, Any]:
    calendar = inspector.partition_calendar
    if calendar is None:
        return {
            "inspector": inspector,
            "block_id": block_id("partition", inspector.selection_token),
            "calendar": None,
        }

    return {
        "inspector": inspector,
        "block_id": block_id("partition", inspector.selection_token),
        "calendar": calendar,
        "last_synced": _format_last_synced(calendar),
        "median": _format_median(calendar),
        "status_label": partition_status_label(calendar),
        "status_class": partition_status_class(calendar),
        "month_groups": _build_month_groups(calendar.months),
    }


def _format_median(calendar: ModelPartitionCalendarDTO) -> str:
    if calendar.median_row_count is None:
        return "No data"
    if calendar.median_row_count.is_integer():
        return str(int(calendar.median_row_count))
    return f"{calendar.median_row_count:.1f}"


def _format_last_synced(calendar: ModelPartitionCalendarDTO) -> str:
    if calendar.last_synced_at is None:
        return "No sync yet"
    return calendar.last_synced_at.strftime("%Y-%m-%d %H:%M:%S MSK")


def _build_month_groups(months: list[PartitionMonthDTO]) -> list[dict[str, Any]]:
    return [
        {
            "year": months_in_year[0].year,
            "months": [_build_month(month) for month in months_in_year],
        }
        for months_in_year in group_months_by_year(months)
    ]


def _build_month(month: PartitionMonthDTO) -> dict[str, Any]:
    return {
        "month_label": month.month_label,
        "leading_empty_days": range(month.leading_empty_days),
        "days": [_build_day(day) for day in month.days],
    }


def _build_day(day: PartitionDayCellDTO) -> dict[str, str]:
    title = (
        f"{day.date.isoformat()} - {day.row_count} rows"
        if day.row_count is not None
        else f"{day.date.isoformat()} - No data"
    )
    return {
        "title": title,
        "fill_class": partition_fill_class(day.fill_level),
    }
