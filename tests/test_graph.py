from pathlib import Path

from dbt_dag.graph.builder import build_graph
from dbt_dag.graph.builder import classify_node
from dbt_dag.manifest.parser import load_manifest


def test_graph_builder_emits_stable_nodes_and_edges(dbt_project: Path) -> None:
    manifest = load_manifest(dbt_project / "target" / "manifest.json")

    graph = build_graph(manifest)

    assert graph.columns == ["sources", "stg", "int", "marts", "exposures", "other"]
    assert graph.project.models_count == 2
    assert graph.project.sources_count == 1
    assert graph.project.tests_count == 1
    assert {node.node_id for node in graph.nodes} == {
        "source.demo.raw.orders",
        "model.demo.stg_orders",
        "model.demo.fct_orders",
    }
    assert {edge.edge_id for edge in graph.edges} == {
        "source.demo.raw.orders->model.demo.stg_orders",
        "model.demo.stg_orders->model.demo.fct_orders",
    }


def test_node_classifier_maps_required_columns(dbt_project: Path) -> None:
    manifest = load_manifest(dbt_project / "target" / "manifest.json")

    nodes = manifest.graph_nodes()

    assert classify_node(nodes["source.demo.raw.orders"]) == "sources"
    assert classify_node(nodes["model.demo.stg_orders"]) == "stg"
    assert classify_node(nodes["model.demo.fct_orders"]) == "marts"
