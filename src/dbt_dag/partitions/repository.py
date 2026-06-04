from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from dbt_dag.db.models import ModelPartitionSnapshotRecord
from dbt_dag.db.models import ModelPartitionSyncStateRecord
from dbt_dag.partitions.models import ModelPartitionSnapshot
from dbt_dag.partitions.models import ModelPartitionSyncState
from dbt_dag.partitions.models import PartitionSnapshotRow
from dbt_dag.partitions.models import PartitionSyncStatus
from dbt_dag.shared.time import MSK
from dbt_dag.shared.time import normalize_to_msk
from dbt_dag.shared.time import now_msk


class ModelPartitionRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_snapshot(self, model_unique_id: str) -> list[ModelPartitionSnapshot]:
        with self._session_factory() as session:
            records: Sequence[ModelPartitionSnapshotRecord] = (
                session.query(ModelPartitionSnapshotRecord)
                .filter(ModelPartitionSnapshotRecord.model_unique_id == model_unique_id)
                .order_by(
                    ModelPartitionSnapshotRecord.partition_date,
                    ModelPartitionSnapshotRecord.partition_key,
                )
                .all()
            )
            return [self._to_snapshot(record) for record in records]

    def get_sync_state(self, model_unique_id: str) -> ModelPartitionSyncState | None:
        with self._session_factory() as session:
            record = (
                session.query(ModelPartitionSyncStateRecord)
                .filter(ModelPartitionSyncStateRecord.model_unique_id == model_unique_id)
                .one_or_none()
            )
            return self._to_sync_state(record) if record is not None else None

    def mark_running(self, model_unique_id: str) -> None:
        with self._session_factory() as session:
            record = self._get_or_create_sync_state(session, model_unique_id)
            timestamp = now_msk()
            record.sync_status = PartitionSyncStatus.RUNNING.value
            record.last_checked_at = timestamp
            record.last_error = ""
            session.commit()

    def replace_snapshot(
        self,
        model_unique_id: str,
        snapshot_rows: list[PartitionSnapshotRow],
    ) -> None:
        with self._session_factory() as session:
            synced_at = now_msk()
            session.execute(
                delete(ModelPartitionSnapshotRecord).where(
                    ModelPartitionSnapshotRecord.model_unique_id == model_unique_id
                )
            )
            for row in snapshot_rows:
                session.add(
                    ModelPartitionSnapshotRecord(
                        model_unique_id=model_unique_id,
                        partition_date=row.partition_date,
                        partition_key=row.partition_key,
                        row_count=row.row_count,
                        source_inserted_at=row.source_inserted_at,
                        synced_at=synced_at,
                    )
                )
            sync_state = self._get_or_create_sync_state(session, model_unique_id)
            sync_state.last_source_inserted_at = _latest_source_inserted_at(snapshot_rows)
            sync_state.last_synced_at = synced_at
            sync_state.last_checked_at = synced_at
            sync_state.sync_status = PartitionSyncStatus.SUCCEEDED.value
            sync_state.last_error = ""
            session.commit()

    def mark_failed(self, model_unique_id: str, error_message: str) -> None:
        with self._session_factory() as session:
            record = self._get_or_create_sync_state(session, model_unique_id)
            record.last_checked_at = now_msk()
            record.sync_status = PartitionSyncStatus.FAILED.value
            record.last_error = error_message
            session.commit()

    def last_synced_model_ids(self, limit: int = 1000) -> list[str]:
        with self._session_factory() as session:
            records: Sequence[ModelPartitionSyncStateRecord] = (
                session.query(ModelPartitionSyncStateRecord)
                .order_by(desc(ModelPartitionSyncStateRecord.last_checked_at))
                .limit(limit)
                .all()
            )
            return [record.model_unique_id for record in records]

    def _get_or_create_sync_state(
        self,
        session: Session,
        model_unique_id: str,
    ) -> ModelPartitionSyncStateRecord:
        record = (
            session.query(ModelPartitionSyncStateRecord)
            .filter(ModelPartitionSyncStateRecord.model_unique_id == model_unique_id)
            .one_or_none()
        )
        if record is not None:
            return record
        record = ModelPartitionSyncStateRecord(
            model_unique_id=model_unique_id,
            last_source_inserted_at=None,
            last_synced_at=None,
            last_checked_at=None,
            sync_status=PartitionSyncStatus.IDLE.value,
            last_error="",
        )
        session.add(record)
        session.flush()
        return record

    def _to_snapshot(self, record: ModelPartitionSnapshotRecord) -> ModelPartitionSnapshot:
        return ModelPartitionSnapshot(
            model_unique_id=record.model_unique_id,
            partition_key=record.partition_key,
            partition_date=record.partition_date,
            row_count=record.row_count,
            source_inserted_at=_normalize_datetime(record.source_inserted_at),
            synced_at=normalize_to_msk(record.synced_at),
        )

    def _to_sync_state(self, record: ModelPartitionSyncStateRecord) -> ModelPartitionSyncState:
        return ModelPartitionSyncState(
            model_unique_id=record.model_unique_id,
            last_source_inserted_at=_normalize_datetime(record.last_source_inserted_at),
            last_synced_at=_normalize_datetime(record.last_synced_at),
            last_checked_at=_normalize_datetime(record.last_checked_at),
            sync_status=PartitionSyncStatus(record.sync_status),
            last_error=record.last_error,
        )


def _latest_source_inserted_at(snapshot_rows: list[PartitionSnapshotRow]) -> datetime | None:
    values = [row.source_inserted_at for row in snapshot_rows if row.source_inserted_at is not None]
    return max(values) if values else None


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=MSK)
    return normalize_to_msk(value)
