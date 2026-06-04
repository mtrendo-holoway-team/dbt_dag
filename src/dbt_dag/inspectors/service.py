from dbt_dag.inspectors.dto import NodeInspectorContextDTO
from dbt_dag.manifest.models import DbtManifestNode
from dbt_dag.metadata.models import empty_node_runtime_metadata
from dbt_dag.metadata.models import NodeRuntimeMetadata
from dbt_dag.partitions.models import ModelPartitionCalendarDTO
from dbt_dag.tasks.models import NodeTaskDTO
from dbt_dag.web.state import AppState


class NodeInspectorContextFactory:
    def build(
        self,
        state: AppState,
        node_id: str,
        selection_token: str,
        *,
        include_tasks: bool = False,
        include_partition_calendar: bool = False,
    ) -> NodeInspectorContextDTO:
        snapshot = state.graph_store.snapshot()
        node = snapshot.manifest.graph_nodes()[node_id]
        runtime = snapshot.runtime_metadata.get(node_id) or empty_node_runtime_metadata()
        supports_partitions = self._supports_partitions(state, node)
        return NodeInspectorContextDTO(
            selection_token=selection_token,
            node=node,
            runtime=runtime,
            tasks=self._build_tasks(state, node_id, include_tasks=include_tasks),
            partition_calendar=self._build_partition_calendar(
                state=state,
                node=node,
                runtime=runtime,
                supports_partitions=supports_partitions,
                include_partition_calendar=include_partition_calendar,
            ),
            supports_partitions=supports_partitions,
        )

    def _supports_partitions(self, state: AppState, node: DbtManifestNode) -> bool:
        return node.resource_type == "model" and state.partition_service.supports_partitions()

    def _build_partition_calendar(
        self,
        state: AppState,
        node: DbtManifestNode,
        runtime: NodeRuntimeMetadata,
        supports_partitions: bool,
        include_partition_calendar: bool,
    ) -> ModelPartitionCalendarDTO | None:
        if not include_partition_calendar or not supports_partitions:
            return None
        calendar = state.partition_service.build_calendar(node.unique_id, runtime.last_updated_at)
        if calendar.is_stale and not calendar.is_refreshing:
            state.partition_runner.start_refresh(node.unique_id)
            calendar = state.partition_service.build_calendar(
                node.unique_id, runtime.last_updated_at
            )
        return calendar

    def _build_tasks(
        self,
        state: AppState,
        node_id: str,
        *,
        include_tasks: bool,
    ) -> list[NodeTaskDTO]:
        if not include_tasks:
            return []
        return state.task_repository.list_for_node(node_id)
