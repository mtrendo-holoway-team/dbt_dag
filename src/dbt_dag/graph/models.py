from dataclasses import dataclass

GRAPH_COLUMNS = ["sources", "stg", "int", "marts", "exposures", "other"]


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    label: str
    column: str
    resource_type: str
    description: str
    indicators: list[str]


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    source: str
    target: str


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
    project: ProjectSummary
