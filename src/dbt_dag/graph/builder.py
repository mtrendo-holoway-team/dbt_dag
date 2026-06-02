from dbt_dag.graph.models import GRAPH_COLUMNS
from dbt_dag.graph.models import GraphEdge
from dbt_dag.graph.models import GraphNode
from dbt_dag.graph.models import GraphPayload
from dbt_dag.graph.models import ProjectSummary
from dbt_dag.manifest.models import DbtManifest
from dbt_dag.manifest.models import DbtManifestNode


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


def build_graph(manifest: DbtManifest) -> GraphPayload:
    graph_nodes = manifest.graph_nodes()
    nodes = [
        GraphNode(
            node_id=node.unique_id,
            label=node.name,
            column=classify_node(node),
            resource_type=node.resource_type,
            description=node.description,
            indicators=[],
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
