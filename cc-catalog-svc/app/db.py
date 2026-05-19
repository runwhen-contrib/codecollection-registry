"""
SQLAlchemy 2.0 sync engine + session factory.

Sync rather than async because:
  - The scheduler (APScheduler) drives polling on a background thread pool
    and shells out to `crane`, which is blocking I/O. There is no benefit
    to async here and significant cognitive cost.
  - FastAPI handlers that read the catalog touch <10 rows per request and
    are cheap; a sync session in a thread is fine.

SQLite-friendly engine settings:
  - `check_same_thread=False` because FastAPI dispatches request handlers
    onto a thread pool. SQLAlchemy serializes access via the pool.
  - WAL pragma is applied on connect for better read/write concurrency.

Postgres is supported by simply pointing `CC_CATALOG_DB_URL` at it; we
keep the engine creation path identical other than the dialect-specific
connect_args.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _build_engine(db_url: str) -> Engine:
    connect_args: dict = {}
    if db_url.startswith("sqlite"):
        # FastAPI + APScheduler share the engine across threads.
        connect_args["check_same_thread"] = False

    engine = create_engine(
        db_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )

    if db_url.startswith("sqlite"):
        # WAL mode lets the catalog API read while the scheduler writes.
        # NORMAL synchronous mode is safe for our throughput and avoids
        # the fsync-per-commit cost of FULL.
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _conn_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings().db_url)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def init_db() -> None:
    """Create all tables. Idempotent.

    We intentionally use `Base.metadata.create_all` rather than Alembic
    for the first cut: the schema is small (5 tables), single-writer
    (the scheduler), and the service is greenfield. When the schema
    starts evolving we'll add Alembic; until then `create_all` keeps the
    bootstrap path trivial.
    """
    engine = get_engine()
    logger.info("initializing schema on %s", _safe_dsn(str(engine.url)))
    Base.metadata.create_all(engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session context. Commits on success, rolls back on
    error, always closes. Use this everywhere outside of FastAPI request
    handlers (those get a session via the `db_session` dependency)."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def db_session() -> Iterator[Session]:
    """FastAPI dependency. Does NOT auto-commit — handlers should be
    read-mostly, and the few writers (admin sync triggers) commit
    explicitly."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
    finally:
        session.close()


def _safe_dsn(url: str) -> str:
    """Strip credentials from a DSN for log lines."""
    if "@" not in url:
        return url
    scheme, _, rest = url.partition("://")
    _, _, host = rest.partition("@")
    return f"{scheme}://***@{host}"
