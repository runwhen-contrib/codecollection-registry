"""
Tiny admin-auth dependency.

The catalog API is read-only and unauthenticated by design (matches the
existing cc-registry-v2 PAPI contract). The mirror API has a small
number of POST endpoints that trigger work; those go through this
dependency so only an operator with `CC_CATALOG_ADMIN_TOKEN` can run
them.

If `CC_CATALOG_ADMIN_TOKEN` is empty (default), admin endpoints return
503. This is the "service is read-only" mode that lets you ship the
container into an environment where you haven't yet decided what auth
to put in front of write endpoints.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_admin(
    authorization: Optional[str] = Header(default=None),
) -> None:
    """Bearer-token check for admin endpoints. Constant-time compare."""
    settings = get_settings()
    expected = settings.admin_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "admin endpoints are disabled (set CC_CATALOG_ADMIN_TOKEN to enable)"
            ),
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:].strip()
    if not _ct_eq(token, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid admin token",
        )


def _ct_eq(a: str, b: str) -> bool:
    """Constant-time string compare for token verification."""
    import hmac
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
