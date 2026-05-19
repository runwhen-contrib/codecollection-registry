"""
Health endpoints.

  /healthz — liveness. Always 200 if the process is up.
  /readyz  — readiness. 200 only when the DB is reachable. K8s readiness
             probes block traffic until readyz succeeds.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/healthz")
def liveness() -> dict:
    """Cheapest possible probe: are we serving HTTP at all."""
    return {"status": "ok"}


@router.get("/readyz")
def readiness() -> dict:
    """Touch the DB to confirm we're ready to serve catalog reads."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        logger.exception("readyz: DB ping failed")
        raise HTTPException(503, detail=f"db unreachable: {exc!r}")
