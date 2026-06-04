from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class RuntimeDataSource(StrEnum):
    WAREHOUSE = "warehouse"
    RUN_RESULTS = "run_results"
    NONE = "none"


class RuntimeFreshness(StrEnum):
    LAST_2H = "last_2h"
    LAST_24H = "last_24h"
    STALE = "stale"
    UNKNOWN = "unknown"


FRESHNESS_COLORS = {
    RuntimeFreshness.LAST_2H: "#22c55e",
    RuntimeFreshness.LAST_24H: "#15803d",
    RuntimeFreshness.STALE: "#eab308",
    RuntimeFreshness.UNKNOWN: "#a1a1aa",
}


@dataclass(frozen=True)
class PartialRuntimeMetadata:
    execution_time_seconds: float | None
    execution_time_source: RuntimeDataSource
    last_updated_at: datetime | None
    last_updated_source: RuntimeDataSource


@dataclass(frozen=True)
class NodeRuntimeMetadata:
    execution_time_seconds: float | None
    execution_time_source: RuntimeDataSource
    last_updated_at: datetime | None
    last_updated_source: RuntimeDataSource
    freshness: RuntimeFreshness
    border_width_px: float
    border_color: str


def empty_partial_metadata() -> PartialRuntimeMetadata:
    return PartialRuntimeMetadata(
        execution_time_seconds=None,
        execution_time_source=RuntimeDataSource.NONE,
        last_updated_at=None,
        last_updated_source=RuntimeDataSource.NONE,
    )


def empty_node_runtime_metadata() -> NodeRuntimeMetadata:
    return NodeRuntimeMetadata(
        execution_time_seconds=None,
        execution_time_source=RuntimeDataSource.NONE,
        last_updated_at=None,
        last_updated_source=RuntimeDataSource.NONE,
        freshness=RuntimeFreshness.UNKNOWN,
        border_width_px=1,
        border_color=FRESHNESS_COLORS[RuntimeFreshness.UNKNOWN],
    )
