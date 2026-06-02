import json
from pathlib import Path
from typing import Any

from dbt_dag.manifest.models import DbtManifest
from dbt_dag.manifest.models import DbtManifestNode


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _parse_node(raw: dict[str, Any]) -> DbtManifestNode:
    depends_on = raw.get("depends_on") or {}
    depends_on_nodes = depends_on.get("nodes") if isinstance(depends_on, dict) else []
    return DbtManifestNode(
        unique_id=str(raw.get("unique_id", "")),
        name=str(raw.get("name", "")),
        resource_type=str(raw.get("resource_type", "")),
        description=str(raw.get("description") or ""),
        depends_on=_as_str_list(depends_on_nodes),
        package_name=str(raw.get("package_name", "")),
        path=str(raw.get("path", "")),
        fqn=_as_str_list(raw.get("fqn")),
        raw=raw,
    )


def _parse_node_mapping(raw_mapping: Any) -> dict[str, DbtManifestNode]:
    if not isinstance(raw_mapping, dict):
        return {}
    return dict(_iter_parsed_nodes(raw_mapping))


def _iter_parsed_nodes(raw_mapping: dict[Any, Any]) -> list[tuple[str, DbtManifestNode]]:
    parsed = []
    for unique_id, raw_node in raw_mapping.items():
        node = _parse_mapping_item(unique_id, raw_node)
        if node is not None:
            parsed.append(node)
    return parsed


def _parse_mapping_item(unique_id: Any, raw_node: Any) -> tuple[str, DbtManifestNode] | None:
    if not isinstance(unique_id, str) or not isinstance(raw_node, dict):
        return None
    node = _parse_node(raw_node)
    if not node.unique_id:
        return None
    return unique_id, node


def load_manifest(path: Path) -> DbtManifest:
    with path.open(encoding="utf-8") as file:
        raw = json.load(file)
    if not isinstance(raw, dict):
        raise ValueError("manifest.json must contain an object")
    return DbtManifest(
        nodes=_parse_node_mapping(raw.get("nodes")),
        sources=_parse_node_mapping(raw.get("sources")),
        exposures=_parse_node_mapping(raw.get("exposures")),
    )
