from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from dbt_dag.db.models import Base


def create_db_engine(sqlite_path: Path) -> Engine:
    return create_engine(f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False})


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
