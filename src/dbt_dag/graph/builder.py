from dbt_dag.graph.models import GRAPH_COLUMNS
from dbt_dag.graph.models import GraphEdge
from dbt_dag.graph.models import GraphNode
from dbt_dag.graph.models import GraphNodeRuntime
from dbt_dag.graph.models import GraphPayload
from dbt_dag.graph.models import ProjectSummary
from dbt_dag.manifest.models import DbtManifest
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.metadata.models import empty_node_runtime_metadata
from dbt_dag.metadata.models import NodeRuntimeMetadata


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
) -> GraphPayload:
    graph_nodes = manifest.graph_nodes()
    nodes = [
        GraphNode(
            node_id=node.unique_id,
            label=node.name,
            column=classify_node(node),
            resource_type=node.resource_type,
            package_name=node.package_name,
            description=node.description,
            indicators=[],
            runtime=_graph_runtime(
                runtime_metadata.get(node.unique_id)
                if runtime_metadata is not None
                else empty_node_runtime_metadata()
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
        project=ProjectSummary(
            models_count=sum(
                1 for node in manifest.nodes.values() if node.resource_type == "model"
            ),
            sources_count=len(manifest.sources),
            tests_count=manifest.test_count(),
        ),
    )


def _graph_runtime(metadata: NodeRuntimeMetadata | None) -> GraphNodeRuntime:
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
