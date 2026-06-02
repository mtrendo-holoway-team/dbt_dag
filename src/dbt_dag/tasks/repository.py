from collections.abc import Sequence

from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from dbt_dag.db.models import NodeTaskRecord
from dbt_dag.shared.time import now_msk
from dbt_dag.tasks.models import NodeTaskDTO
from dbt_dag.tasks.models import TaskStatus


class NodeTaskRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, node_id: str, command: str) -> NodeTaskDTO:
        with self._session_factory() as session:
            record = NodeTaskRecord(
                node_id=node_id,
                command=command,
                status=TaskStatus.CREATED.value,
                created_at=now_msk(),
                logs_excerpt="",
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return self._to_dto(record)

    def mark_running(self, task_id: int) -> None:
        with self._session_factory() as session:
            record = session.get(NodeTaskRecord, task_id)
            if record is None:
                return
            record.status = TaskStatus.RUNNING.value
            record.started_at = now_msk()
            session.commit()

    def mark_finished(self, task_id: int, exit_code: int, logs_excerpt: str) -> None:
        with self._session_factory() as session:
            record = session.get(NodeTaskRecord, task_id)
            if record is None:
                return
            record.status = (
                TaskStatus.SUCCEEDED.value if exit_code == 0 else TaskStatus.FAILED.value
            )
            record.exit_code = exit_code
            record.finished_at = now_msk()
            record.logs_excerpt = logs_excerpt[-4000:]
            session.commit()

    def list_for_node(self, node_id: str, limit: int = 10) -> list[NodeTaskDTO]:
        with self._session_factory() as session:
            records: Sequence[NodeTaskRecord] = (
                session.query(NodeTaskRecord)
                .filter(NodeTaskRecord.node_id == node_id)
                .order_by(desc(NodeTaskRecord.created_at))
                .limit(limit)
                .all()
            )
            return [self._to_dto(record) for record in records]

    def _to_dto(self, record: NodeTaskRecord) -> NodeTaskDTO:
        return NodeTaskDTO(
            task_id=record.record_id,
            node_id=record.node_id,
            command=record.command,
            status=TaskStatus(record.status),
            created_at=record.created_at,
            started_at=record.started_at,
            finished_at=record.finished_at,
            exit_code=record.exit_code,
            logs_excerpt=record.logs_excerpt,
        )
