from dataclasses import dataclass
from datetime import datetime

from dbt_dag.metadata.models import RuntimeDataSource
from dbt_dag.metadata.models import RuntimeFreshness

GRAPH_COLUMNS = ["sources", "stg", "int", "marts", "exposures", "other"]


@dataclass(frozen=True)
class GraphNodeRuntime:
    execution_time_seconds: float | None
    execution_time_source: RuntimeDataSource
    last_updated_at: datetime | None
    last_updated_source: RuntimeDataSource
    status_icon_name: str
    status_color_hex: str
    freshness: RuntimeFreshness
    border_width_px: float
    border_color: str


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    label: str
    type_badge: str
    column: str
    resource_type: str
    package_name: str
    description: str
    indicators: list[str]
    runtime: GraphNodeRuntime


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    source: str
    target: str


@dataclass(frozen=True)
class GraphGroup:
    group_id: str
    label: str
    node_ids: list[str]


@dataclass(frozen=True)
class ProjectSummary:
    models_count: int
    sources_count: int
    tests_count: int


@dataclass(frozen=True)
class GraphPayload:
    columns: list[str]
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    groups: list[GraphGroup]
    project: ProjectSummary
