"""
FastAPI application entrypoint.

  uvicorn app.main:app --host 0.0.0.0 --port 8080

Lifespan:

  startup  — load config, init DB, start scheduler
  shutdown — stop scheduler, dispose engine

Run modes:

  Normal     — the scheduler runs in the same process as the API. This is
               the default and the only mode for v1.
  API-only   — set CC_CATALOG_DISABLE_SCHEDULER=1 to skip starting the
               scheduler. Useful when running 2+ API replicas behind a
               load balancer and a single dedicated scheduler pod.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.config import get_settings, load_config, get_config
from app.db import get_engine, init_db
from app.routers import admin, catalog, git, health, mirror
from app.scheduler import start_scheduler, stop_scheduler


def _configure_logging() -> None:
    level = getattr(logging, get_settings().log_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    logger = logging.getLogger("cc-catalog-svc")
    logger.info("starting cc-catalog-svc v%s", __version__)

    load_config()
    init_db()

    cfg = get_config()
    if cfg.git.enabled:
        from a2wsgi import WSGIMiddleware

        from app.git_http import make_git_wsgi_app

        mount = cfg.git.mount_path.rstrip("/") or "/git"
        # Dulwich git smart HTTP uses the WSGI write() callback; Starlette's
        # deprecated WSGIMiddleware returns None from start_response and drops
        # streamed pack data (git clone fails with "transfer closed").
        app.mount(mount, WSGIMiddleware(make_git_wsgi_app(cfg.git.data_dir)))
        logger.info("git smart HTTP mounted at %s (data_dir=%s)", mount, cfg.git.data_dir)

    if os.environ.get("CC_CATALOG_DISABLE_SCHEDULER", "").lower() not in (
        "1",
        "true",
        "yes",
    ):
        start_scheduler()
    else:
        logger.info("scheduler disabled (CC_CATALOG_DISABLE_SCHEDULER set)")

    try:
        yield
    finally:
        stop_scheduler()
        try:
            get_engine().dispose()
        except Exception:
            logger.exception("engine.dispose() failed during shutdown")


app = FastAPI(
    title="cc-catalog-svc",
    description=(
        "Self-contained CodeCollection image catalog + mirror microservice. "
        "PAPI-compatible catalog API, optional git mirror hosting for air-gapped "
        "deployments, and a destination plugin system for mirroring images into "
        "customer registries (JFrog Artifactory in v1)."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(health.router)
app.include_router(catalog.router)
app.include_router(mirror.router)
app.include_router(git.router)
app.include_router(admin.router)


def run() -> None:  # pragma: no cover - thin wrapper for `cc-catalog-svc` script
    """Entry point for the `cc-catalog-svc` console script."""
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.host,
        port=s.port,
        log_level=s.log_level.lower(),
    )
