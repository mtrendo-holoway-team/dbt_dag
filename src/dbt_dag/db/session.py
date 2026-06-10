from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import Engine
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

from dbt_dag.db.models import Base


def create_db_engine(sqlite_path: Path) -> Engine:
    return create_engine(f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False})


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    _ensure_partition_snapshot_compatibility(engine)


def _ensure_partition_snapshot_compatibility(engine: Engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "model_partition_snapshots" not in table_names:
        return
    column_names = {
        str(column["name"])
        for column in inspector.get_columns("model_partition_snapshots")
        if column.get("name") is not None
    }
    if "partition_updated_at" in column_names:
        return
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE model_partition_snapshots " "ADD COLUMN partition_updated_at DATETIME"
            )
        )
