from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.storage.models import Base


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
