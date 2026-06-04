from dataclasses import dataclass

from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.metadata.models import NodeRuntimeMetadata
from dbt_dag.partitions.models import ModelPartitionCalendarDTO
from dbt_dag.tasks.models import NodeTaskDTO


@dataclass(frozen=True)
class NodeInspectorContextDTO:
    selection_token: str
    node: DbtManifestNode
    runtime: NodeRuntimeMetadata
    tasks: list[NodeTaskDTO]
    partition_calendar: ModelPartitionCalendarDTO | None
    supports_partitions: bool
