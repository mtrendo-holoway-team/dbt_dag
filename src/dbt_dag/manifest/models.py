from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DbtManifestNode:
    unique_id: str
    name: str
    resource_type: str
    description: str
    depends_on: list[str]
    package_name: str
    path: str
    fqn: list[str]
    raw: dict[str, Any]


@dataclass(frozen=True)
class DbtManifest:
    nodes: dict[str, DbtManifestNode]
    sources: dict[str, DbtManifestNode]
    exposures: dict[str, DbtManifestNode]

    def graph_nodes(self) -> dict[str, DbtManifestNode]:
        return {
            node_id: node
            for node_id, node in [
                *self.nodes.items(),
                *self.sources.items(),
                *self.exposures.items(),
            ]
            if node.resource_type in {"model", "source", "exposure"}
        }

    def test_count(self) -> int:
        return sum(1 for node in self.nodes.values() if node.resource_type == "test")
