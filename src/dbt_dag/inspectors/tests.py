from typing import Any

from dbt_dag.inspectors.dto import NodeInspectorContextDTO
from dbt_dag.inspectors.utils import block_id
from dbt_dag.inspectors.utils import test_status_dot_class
from dbt_dag.inspectors.utils import test_status_label
from dbt_dag.tests.models import ModelTestStatus

TEMPLATE_NAME = "inspectors/blocks/tests.html"


def build_template_context(inspector: NodeInspectorContextDTO) -> dict[str, Any]:
    summary = inspector.tests
    tests = []
    if summary is not None:
        tests = [
            {
                "name": test.test_name,
                "dot_class": test_status_dot_class(test.status),
                "status_label": test_status_label(test.status),
                "executed_at": (
                    test.executed_at.strftime("%Y-%m-%d %H:%M:%S MSK")
                    if test.executed_at is not None
                    else "Нет запусков"
                ),
            }
            for test in summary.tests
        ]
    return {
        "inspector": inspector,
        "block_id": block_id("tests", inspector.selection_token),
        "summary": summary,
        "tests": tests,
        "tests_loading": inspector.tests_loading,
        "loading_class": " status-dot-loading" if inspector.tests_loading else "",
        "missing_status": ModelTestStatus.MISSING,
        "summary_dot_class": (
            test_status_dot_class(summary.status)
            if summary is not None
            else test_status_dot_class(ModelTestStatus.MISSING)
        ),
        "summary_label": (
            test_status_label(summary.status)
            if summary is not None
            else test_status_label(ModelTestStatus.MISSING)
        ),
    }
