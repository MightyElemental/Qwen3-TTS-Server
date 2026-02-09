# app/core/db.py
from __future__ import annotations

from typing import Generator

from fastapi import Depends
from sqlmodel import SQLModel, Session, create_engine

_engine = None


def init_db(db_path):
    global _engine
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(_engine)


def get_session() -> Generator[Session, None, None]:
    if _engine is None:
        raise RuntimeError("DB not initialized")
    with Session(_engine) as session:
        yield session


SessionDep = Depends(get_session)