from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(String(64), primary_key=True)
    repo_url = Column(String(500), nullable=False)
    owner = Column(String(120), nullable=False, default="")
    repo = Column(String(200), nullable=False, default="")
    branch = Column(String(200), nullable=False, default="main")
    status = Column(String(32), nullable=False, default="queued")
    progress_pct = Column(Integer, nullable=False, default=0)
    current_step = Column(String(200), nullable=False, default="")
    debt_score = Column(Float, nullable=True)
    grade = Column(String(2), nullable=True)
    ai_generated_pct = Column(Float, nullable=True)
    result_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    encrypted_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DeepScan(Base):
    __tablename__ = "deep_scans"

    id = Column(String(64), primary_key=True)
    analysis_id = Column(String(64), nullable=False, index=True)
    ip = Column(String(64), nullable=False, default="")
    status = Column(String(32), nullable=False, default="queued")
    memo_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        is_sqlite = settings.database_url.startswith("sqlite")
        connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
        _engine = create_engine(
            settings.database_url,
            connect_args=connect_args,
            future=True,
            pool_pre_ping=True,
        )
        if is_sqlite:
            @event.listens_for(_engine, "connect")
            def _set_sqlite_pragmas(dbapi_connection, _record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        Base.metadata.create_all(_engine)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return _engine


def get_session() -> Session:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def dump_result(obj) -> str:
    return json.dumps(obj, default=str)


def load_result(raw: str | None):
    if not raw:
        return None
    return json.loads(raw)
