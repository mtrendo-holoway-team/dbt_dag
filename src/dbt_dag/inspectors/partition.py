from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Any

from dbt_dag.inspectors.dto import NodeInspectorContextDTO
from dbt_dag.inspectors.utils import (
    block_id,
    group_months_by_year,
    partition_status_class,
    partition_status_label,
)
from dbt_dag.partitions.models import (
    ModelPartitionCalendarDTO,
    PartitionDayCellDTO,
    PartitionMonthDTO,
)

TEMPLATE_NAME = "inspectors/blocks/partition.html"
_REFERENCE_WINDOW = 7
_COLOR_THRESHOLDS = (
    (0.25, "partition-day-critical"),
    (0.8, "partition-day-low"),
    (1.2, "partition-day-normal"),
)


@dataclass(frozen=True)
class _DayReference:
    day: PartitionDayCellDTO
    reference_median: float | None


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
        "month_groups": _build_month_groups(
            calendar.months,
            calendar.median_row_count,
            current_date=calendar.range_end,
        ),
    }


def _format_median(calendar: ModelPartitionCalendarDTO) -> str:
    if calendar.median_row_count is None:
        return "Нет данных"
    if calendar.median_row_count.is_integer():
        return str(int(calendar.median_row_count))
    return f"{calendar.median_row_count:.1f}"


def _format_last_synced(calendar: ModelPartitionCalendarDTO) -> str:
    if calendar.last_synced_at is None:
        return "Не синхронизировано"
    return calendar.last_synced_at.strftime("%Y-%m-%d %H:%M:%S MSK")


def _build_month_groups(
    months: list[PartitionMonthDTO],
    overall_median_row_count: float | None,
    current_date: date,
) -> list[dict[str, Any]]:
    reference_median_by_date = _reference_median_by_date(months)
    use_simple_presence_colors = _use_simple_presence_colors(overall_median_row_count)
    return [
        {
            "year": months_in_year[0].year,
            "months": [
                _build_month(
                    month,
                    reference_median_by_date,
                    use_simple_presence_colors,
                    current_date,
                )
                for month in months_in_year
            ],
        }
        for months_in_year in group_months_by_year(months)
    ]


def _build_month(
    month: PartitionMonthDTO,
    reference_median_by_date: dict[str, float | None],
    use_simple_presence_colors: bool,
    current_date: date,
) -> dict[str, Any]:
    return {
        "month_label": month.month_label,
        "leading_empty_days": range(month.leading_empty_days),
        "days": [
            _build_day(day, use_simple_presence_colors, current_date)
            for day in _annotate_reference_medians(month.days, reference_median_by_date)
        ],
    }


def _build_day(
    day_reference: _DayReference,
    use_simple_presence_colors: bool,
    current_date: date,
) -> dict[str, str]:
    day = day_reference.day
    title = (
        f"{day.date.isoformat()} - {day.row_count} строк"
        if day.row_count is not None
        else f"{day.date.isoformat()} - Нет данных"
    )
    return {
        "title": title,
        "color_class": _partition_day_color_class(
            day.row_count,
            day_reference.reference_median,
            use_simple_presence_colors,
            is_current_day=day.date == current_date,
        ),
    }


def _annotate_reference_medians(
    month_days: list[PartitionDayCellDTO],
    reference_median_by_date: dict[str, float | None],
) -> list[_DayReference]:
    return [
        _DayReference(
            day=day,
            reference_median=reference_median_by_date.get(day.date.isoformat()),
        )
        for day in month_days
    ]


def _reference_median_by_date(months: list[PartitionMonthDTO]) -> dict[str, float | None]:
    chronological_days = [day for month in reversed(months) for day in month.days]
    medians: dict[str, float | None] = {}
    for index, day in enumerate(chronological_days):
        medians[day.date.isoformat()] = _reference_median(chronological_days, index)
    return medians


def _reference_median(days: list[PartitionDayCellDTO], current_index: int) -> float | None:
    current_day = days[current_index]
    if current_day.row_count is None:
        return None
    previous_values = [day.row_count for day in days[:current_index] if day.row_count is not None][
        -_REFERENCE_WINDOW:
    ]
    if len(previous_values) < _REFERENCE_WINDOW:
        next_values = [
            day.row_count for day in days[current_index + 1 :] if day.row_count is not None
        ]
        previous_values.extend(next_values[: _REFERENCE_WINDOW - len(previous_values)])
    if not previous_values:
        return None
    return float(median(previous_values))


def _use_simple_presence_colors(overall_median_row_count: float | None) -> bool:
    return overall_median_row_count is not None and overall_median_row_count < 100


def _partition_day_color_class(
    row_count: int | None,
    reference_median: float | None,
    use_simple_presence_colors: bool,
    is_current_day: bool = False,
) -> str:
    if row_count is None:
        if is_current_day:
            return ""
        return "partition-day-no-data"
    if use_simple_presence_colors:
        return "partition-day-normal"
    ratio = _partition_day_ratio(row_count, reference_median)
    if ratio is None:
        return "partition-day-normal"
    return _partition_day_color_by_ratio(ratio)


def _partition_day_ratio(row_count: int, reference_median: float | None) -> float | None:
    if reference_median is None:
        return None
    if reference_median <= 0:
        return None if row_count <= 0 else float("inf")
    return row_count / reference_median


def _partition_day_color_by_ratio(ratio: float) -> str:
    for threshold, color_class in _COLOR_THRESHOLDS:
        if ratio < threshold:
            return color_class
    return "partition-day-high"
