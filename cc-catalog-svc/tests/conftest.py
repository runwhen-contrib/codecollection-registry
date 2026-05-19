"""
Shared pytest fixtures.

Every test gets a clean in-memory SQLite DB so we don't have to manage
test data ordering. The fixtures monkey-patch the module-level
`get_engine` / `get_session_factory` cache so app code talking to
the DB picks up our test engine.
"""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import config as config_mod
from app import db as db_mod
from app.config import AppConfig, get_settings
from app.models import Base


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch, tmp_path):
    """Force every test to a unique sqlite URL + fresh settings cache."""
    db_url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("CC_CATALOG_DB_URL", db_url)
    monkeypatch.setenv("CC_CATALOG_ADMIN_TOKEN", "admin-test-token")
    monkeypatch.setenv("CC_CATALOG_CONFIG_FILE", str(tmp_path / "config.yaml"))
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._SessionLocal = None
    config_mod._CONFIG_CACHE = None
    yield
    get_settings.cache_clear()
    db_mod._engine = None
    db_mod._SessionLocal = None
    config_mod._CONFIG_CACHE = None


@pytest.fixture
def engine():
    """Build the engine + create schema. Tests can pull a session from
    `db_session` or use the engine directly for inspection."""
    eng = create_engine(get_settings().db_url, future=True)
    Base.metadata.create_all(eng)
    db_mod._engine = eng
    db_mod._SessionLocal = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine) -> Iterator[Session]:
    factory = db_mod.get_session_factory()
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def empty_app_config(engine) -> AppConfig:
    cfg = AppConfig()
    config_mod._CONFIG_CACHE = cfg
    return cfg


@pytest.fixture
def client(engine, monkeypatch) -> Iterator[TestClient]:
    """Build a TestClient that skips the scheduler.

    The scheduler is irrelevant to API tests (we drive the underlying
    services directly) and starting it from a unit test makes the test
    process noisy.
    """
    monkeypatch.setenv("CC_CATALOG_DISABLE_SCHEDULER", "1")
    # Import here so the env var is honored.
    from app.main import app

    with TestClient(app) as c:
        yield c
