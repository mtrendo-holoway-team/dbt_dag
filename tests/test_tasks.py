from pathlib import Path

from dbt_dag.db.session import create_db_engine
from dbt_dag.db.session import create_session_factory
from dbt_dag.db.session import init_db
from dbt_dag.tasks.models import TaskStatus
from dbt_dag.tasks.repository import NodeTaskRepository


def test_task_repository_persists_state_transitions(tmp_path: Path) -> None:
    engine = create_db_engine(tmp_path / "tasks.sqlite")
    init_db(engine)
    repository = NodeTaskRepository(create_session_factory(engine))

    task = repository.create("model.demo.stg_orders", "dbt build --select model.demo.stg_orders")
    repository.mark_running(task.task_id)
    repository.mark_finished(task.task_id, exit_code=0, logs_excerpt="done")

    tasks = repository.list_for_node("model.demo.stg_orders")

    assert len(tasks) == 1
    assert tasks[0].status == TaskStatus.SUCCEEDED
    assert tasks[0].exit_code == 0
    assert tasks[0].logs_excerpt == "done"
