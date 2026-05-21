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

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base

logger = logging.getLogger(__name__)

# Columns added after the initial schema cut. ``init_db`` ensures these
# exist on already-deployed databases without requiring a full Alembic
# pipeline. Format: {table_name: {column_name: SQL type for ADD COLUMN}}.
# Keep types portable across sqlite + postgres (no ``SERIAL`` etc.).
_LEGACY_COLUMN_ADDITIONS: dict[str, dict[str, str]] = {
    "codecollections": {
        "git_head_commit": "VARCHAR(80)",
        "git_last_synced": "TIMESTAMP",
        "git_last_sync_error": "TEXT",
    },
}

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
    """Create all tables and apply lightweight in-place migrations.

    We intentionally use ``Base.metadata.create_all`` rather than
    Alembic for the first cut: the schema is small (5 tables),
    single-writer (the scheduler), and the service is greenfield. When
    the schema starts evolving in earnest we'll add Alembic.

    ``create_all`` only creates *missing* tables, so any column added
    to an existing table after the initial release would silently fail
    on upgrade. ``_apply_legacy_column_additions`` patches that gap by
    issuing ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS`` (sqlite + pg
    compatible) for every column registered in
    ``_LEGACY_COLUMN_ADDITIONS``.
    """
    engine = get_engine()
    logger.info("initializing schema on %s", _safe_dsn(str(engine.url)))
    Base.metadata.create_all(engine)
    _apply_legacy_column_additions(engine)


def _apply_legacy_column_additions(engine: Engine) -> None:
    """Idempotently add columns introduced after the initial schema."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table_name, columns in _LEGACY_COLUMN_ADDITIONS.items():
        if table_name not in existing_tables:
            # create_all just made it, so every column is already there.
            continue
        present = {c["name"] for c in inspector.get_columns(table_name)}
        missing = {name: ddl for name, ddl in columns.items() if name not in present}
        if not missing:
            continue
        with engine.begin() as conn:
            for col_name, col_ddl in missing.items():
                logger.info(
                    "init_db: adding missing column %s.%s (%s)",
                    table_name,
                    col_name,
                    col_ddl,
                )
                conn.execute(
                    text(f'ALTER TABLE {table_name} ADD COLUMN {col_name} {col_ddl}')
                )


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
