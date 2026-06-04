from typing import Any

from dbt_dag.inspectors.dto import NodeInspectorContextDTO
from dbt_dag.inspectors.utils import block_id
from dbt_dag.inspectors.utils import source_label

TEMPLATE_NAME = "inspectors/blocks/last_update.html"


def build_template_context(inspector: NodeInspectorContextDTO) -> dict[str, Any]:
    updated_at = (
        inspector.runtime.last_updated_at.strftime("%Y-%m-%d %H:%M:%S MSK")
        if inspector.runtime.last_updated_at is not None
        else "No data"
    )
    execution_time = (
        f"{inspector.runtime.execution_time_seconds:.2f} s"
        if inspector.runtime.execution_time_seconds is not None
        else "No data"
    )
    return {
        "inspector": inspector,
        "block_id": block_id("last-update", inspector.selection_token),
        "updated_at": updated_at,
        "execution_time": execution_time,
        "updated_source": source_label(inspector.runtime.last_updated_source),
        "execution_source": source_label(inspector.runtime.execution_time_source),
    }
