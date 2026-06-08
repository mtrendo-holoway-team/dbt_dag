from dbt_dag.graph.models import GRAPH_COLUMNS
from dbt_dag.graph.models import GraphEdge
from dbt_dag.graph.models import GraphGroup
from dbt_dag.graph.models import GraphNode
from dbt_dag.graph.models import GraphNodeRuntime
from dbt_dag.graph.models import GraphNodeTestIndicator
from dbt_dag.graph.models import GraphPayload
from dbt_dag.graph.models import ProjectSummary
from dbt_dag.manifest.models import DbtManifest
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.metadata.models import empty_node_runtime_metadata
from dbt_dag.metadata.models import NodeRuntimeMetadata
from dbt_dag.tests.models import ModelTestStatus
from dbt_dag.tests.models import ModelTestSummaryDTO


def classify_node(node: DbtManifestNode) -> str:
    if node.resource_type == "source":
        return "sources"
    if node.resource_type == "exposure":
        return "exposures"

    searchable = "/".join([node.path, *node.fqn, node.name]).lower()
    if _is_staging_node(node.name, searchable):
        return "stg"
    if _is_intermediate_node(node.name, searchable):
        return "int"
    if _is_mart_node(node.name, searchable):
        return "marts"
    return "other"


def _is_staging_node(name: str, searchable: str) -> bool:
    return name.startswith(("stg_", "stg__")) or "/stg" in searchable or "staging" in searchable


def _is_intermediate_node(name: str, searchable: str) -> bool:
    return (
        name.startswith(("int_", "int__")) or "/int" in searchable or "intermediate" in searchable
    )


def _is_mart_node(name: str, searchable: str) -> bool:
    return name.startswith(("mart_", "marts_", "fct_", "dim_")) or "marts" in searchable


def build_graph(
    manifest: DbtManifest,
    runtime_metadata: dict[str, NodeRuntimeMetadata] | None = None,
    test_summaries: dict[str, ModelTestSummaryDTO] | None = None,
) -> GraphPayload:
    graph_nodes = manifest.graph_nodes()
    groups = _build_groups(graph_nodes)
    nodes = [
        GraphNode(
            node_id=node.unique_id,
            label=node.name,
            type_badge=node_type_badge(node),
            column=classify_node(node),
            resource_type=node.resource_type,
            package_name=node.package_name,
            description=node.description,
            indicators=[],
            runtime=_graph_runtime(
                (
                    runtime_metadata.get(node.unique_id)
                    if runtime_metadata is not None
                    else empty_node_runtime_metadata()
                ),
            ),
            test_indicator=GraphNodeTestIndicator(
                status=_graph_test_status(node.unique_id, test_summaries),
            ),
        )
        for node in graph_nodes.values()
    ]
    edges = [
        GraphEdge(
            edge_id=f"{dependency}->{node.unique_id}",
            source=dependency,
            target=node.unique_id,
        )
        for node in graph_nodes.values()
        for dependency in node.depends_on
        if dependency in graph_nodes
    ]
    return GraphPayload(
        columns=GRAPH_COLUMNS,
        nodes=nodes,
        edges=edges,
        groups=groups,
        project=ProjectSummary(
            models_count=sum(
                1 for node in manifest.nodes.values() if node.resource_type == "model"
            ),
            sources_count=len(manifest.sources),
            tests_count=manifest.test_count(),
        ),
    )


def node_type_badge(node: DbtManifestNode) -> str:
    if node.resource_type == "source":
        return "S"
    if node.resource_type == "exposure":
        return "X"
    if node.resource_type != "model":
        return (node.resource_type[:1] or "?").upper()

    materialized = str(node.raw.get("config", {}).get("materialized", "")).lower()
    badge_by_materialization = {
        "table": "T",
        "view": "V",
        "ephemeral": "E",
        "materialized_view": "M",
        "incremental": "I",
    }
    return badge_by_materialization.get(materialized, "M")


def _graph_runtime(
    metadata: NodeRuntimeMetadata | None,
) -> GraphNodeRuntime:
    if metadata is None:
        metadata = empty_node_runtime_metadata()
    return GraphNodeRuntime(
        execution_time_seconds=metadata.execution_time_seconds,
        execution_time_source=metadata.execution_time_source,
        last_updated_at=metadata.last_updated_at,
        last_updated_source=metadata.last_updated_source,
        freshness=metadata.freshness,
        border_width_px=metadata.border_width_px,
        border_color=metadata.border_color,
    )


def _graph_test_status(
    node_id: str,
    test_summaries: dict[str, ModelTestSummaryDTO] | None,
) -> ModelTestStatus:
    if test_summaries is None:
        return ModelTestStatus.MISSING
    summary = test_summaries.get(node_id)
    if summary is None:
        return ModelTestStatus.MISSING
    return summary.status


def _build_groups(graph_nodes: dict[str, DbtManifestNode]) -> list[GraphGroup]:
    source_groups = _build_source_groups(graph_nodes)
    product_group = _build_product_group(graph_nodes)
    return [*source_groups, *product_group]


def _build_source_groups(graph_nodes: dict[str, DbtManifestNode]) -> list[GraphGroup]:
    grouped_sources: dict[tuple[str, str], list[str]] = {}
    for node in graph_nodes.values():
        if node.resource_type != "source":
            continue
        source_name = _source_name(node)
        if not source_name:
            continue
        label = _source_group_label(node, source_name)
        grouped_sources.setdefault((source_name, label), []).append(node.unique_id)
    return [
        GraphGroup(
            group_id=f"source:{source_name}",
            label=label,
            node_ids=sorted(node_ids),
        )
        for (source_name, label), node_ids in sorted(grouped_sources.items())
    ]


def _build_product_group(graph_nodes: dict[str, DbtManifestNode]) -> list[GraphGroup]:
    product_node_ids = sorted(
        node.unique_id
        for node in graph_nodes.values()
        if node.resource_type == "model" and "product" in _node_tags(node)
    )
    if not product_node_ids:
        return []
    return [GraphGroup(group_id="tag:product", label="Продукт", node_ids=product_node_ids)]


def _source_name(node: DbtManifestNode) -> str:
    source_name = node.raw.get("source_name")
    return source_name.strip() if isinstance(source_name, str) else ""


def _source_group_label(node: DbtManifestNode, fallback: str) -> str:
    source_description = node.raw.get("source_description")
    if isinstance(source_description, str) and source_description.strip():
        return source_description.strip()
    return fallback


def _node_tags(node: DbtManifestNode) -> set[str]:
    raw_tags = node.raw.get("tags")
    if isinstance(raw_tags, str):
        return {raw_tags}
    if isinstance(raw_tags, list):
        return {tag for tag in raw_tags if isinstance(tag, str)}
    return set()
