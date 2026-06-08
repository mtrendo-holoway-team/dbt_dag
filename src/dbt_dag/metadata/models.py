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
    LAST_48H = "last_48h"
    STALE = "stale"
    UNKNOWN = "unknown"


MODEL_BORDER_COLOR = "#075985"


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
        border_color=MODEL_BORDER_COLOR,
    )
